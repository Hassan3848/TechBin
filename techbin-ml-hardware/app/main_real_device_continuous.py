"""
Continuous TechBin real-device runtime.

This entry point repeatedly runs the verified one-session real-device pipeline,
then requires stable front-sensor absence before rearming. It owns an advisory
process lock for its full lifetime so only one lock-aware camera/GPIO runtime can
run at a time.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TextIO

from app.engine.real_device_pipeline import (
    RealDeviceDisposalPipeline,
    RealDevicePipelineConfig,
)
from app.logger import get_logger
from app.sensors.direct_pi_stack import build_direct_pi_hardware_stack
from scripts.preflight_demo_readiness import main as run_demo_preflight


logger = get_logger(__name__)

DEFAULT_LOCK_PATH = Path("/run/lock/techbin-real-device.lock")


class ContinuousRuntimeError(RuntimeError):
    """Raised when the continuous runtime cannot start or safely continue."""


class RuntimeLockError(ContinuousRuntimeError):
    """Raised when another lock-aware TechBin hardware runtime is active."""


class ShutdownRequested(BaseException):
    """Internal control-flow exception raised by SIGINT/SIGTERM handlers."""

    def __init__(self, signum: int | None = None) -> None:
        self.signum = signum
        super().__init__(f"shutdown_requested:{signum}")


@dataclass(frozen=True)
class RearmConfig:
    clear_reads: int = 3
    poll_seconds: float = 0.45
    delay_seconds: float = 1.0

    def validate(self) -> None:
        if self.clear_reads <= 0:
            raise ContinuousRuntimeError("rearm clear_reads must be greater than zero")
        if self.poll_seconds < 0:
            raise ContinuousRuntimeError("rearm poll_seconds cannot be negative")
        if self.delay_seconds < 0:
            raise ContinuousRuntimeError("rearm delay_seconds cannot be negative")


class RuntimeFileLock:
    """Non-blocking advisory lock held for the daemon process lifetime."""

    def __init__(self, path: str | Path = DEFAULT_LOCK_PATH) -> None:
        self.path = Path(path).expanduser().resolve()
        self._file: TextIO | None = None

    def acquire(self) -> None:
        if self._file is not None:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise RuntimeLockError(
                f"Another TechBin hardware runtime holds {self.path}"
            ) from exc

        self._file = lock_file

    def release(self) -> None:
        if self._file is None:
            return

        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None

    def __enter__(self) -> "RuntimeFileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


def wait_for_front_clear(
    *,
    config: RearmConfig,
    stack_factory: Callable[[], Any] = build_direct_pi_hardware_stack,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Require consecutive valid absence readings before another session."""

    config.validate()
    stack = None
    consecutive_clear = 0

    try:
        stack = stack_factory()
        logger.info(
            "Waiting to rearm | requiredClearReads=%s",
            config.clear_reads,
        )

        while consecutive_clear < config.clear_reads:
            reading = stack.session_detector.update().to_dict()
            is_clear = bool(reading.get("valid")) and reading.get(
                "presenceDetected"
            ) is False

            consecutive_clear = consecutive_clear + 1 if is_clear else 0
            logger.info(
                "Rearm observation | clear=%s | consecutiveClear=%s/%s | distance=%s",
                is_clear,
                consecutive_clear,
                config.clear_reads,
                reading.get("distanceCm"),
            )

            if consecutive_clear < config.clear_reads:
                sleep(config.poll_seconds)

        if config.delay_seconds > 0:
            sleep(config.delay_seconds)

        logger.info("Runtime rearmed after stable front-sensor absence")
    finally:
        if stack is not None:
            close_stack = getattr(stack, "close", None)
            if callable(close_stack):
                try:
                    close_stack()
                except Exception as exc:
                    logger.warning("Failed to close rearm hardware stack: %s", exc)


def emit_event_result(result: Any, *, json_lines: bool) -> None:
    result_data = result.to_dict()
    if json_lines:
        print(
            json.dumps(result_data, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )
        return

    logger.info(
        "Continuous session result | status=%s | processed=%s | eventId=%s | faultCode=%s",
        result_data.get("status"),
        result_data.get("processed"),
        result_data.get("eventId"),
        result_data.get("faultCode"),
    )


def run_continuous_sessions(
    *,
    pipeline: Any,
    rearm_waiter: Callable[[], None],
    result_emitter: Callable[[Any], None],
    max_sessions: int | None = None,
) -> int:
    """Run sessions until an intentional stop or a fatal pipeline result."""

    completed_sessions = 0

    try:
        while True:
            result = pipeline.process_once()
            result_emitter(result)

            if result.status == "fault":
                logger.error(
                    "Continuous runtime stopping after fatal session fault | faultCode=%s | message=%s",
                    result.faultCode,
                    result.message,
                )
                return 1

            completed_sessions += 1
            if max_sessions is not None and completed_sessions >= max_sessions:
                return 0

            rearm_waiter()
    except (KeyboardInterrupt, ShutdownRequested) as exc:
        logger.info("Continuous runtime stopped intentionally | reason=%s", exc)
        return 0
    except Exception:
        logger.exception("Continuous runtime stopped after a fatal error")
        return 1
    finally:
        close_pipeline = getattr(pipeline, "close", None)
        if callable(close_pipeline):
            close_pipeline()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the continuous TechBin Pi real-device daemon."
    )
    parser.add_argument(
        "--telemetry-mode",
        choices=("none", "queue", "upload_or_queue"),
        default="upload_or_queue",
        help="Supabase telemetry handling mode.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print one compact JSON result line per session.",
    )
    parser.add_argument("--rearm-clear-reads", type=int, default=3)
    parser.add_argument("--rearm-poll-seconds", type=float, default=0.45)
    parser.add_argument("--rearm-delay-seconds", type=float, default=1.0)
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK_PATH))
    return parser


def _install_signal_handlers() -> dict[int, Any]:
    previous: dict[int, Any] = {}

    def request_shutdown(signum: int, frame: Any) -> None:
        del frame
        raise ShutdownRequested(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, request_shutdown)

    return previous


def _restore_signal_handlers(previous: dict[int, Any]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def main() -> int:
    args = _build_parser().parse_args()
    previous_handlers = _install_signal_handlers()

    try:
        if run_demo_preflight() != 0:
            logger.error("Continuous runtime preflight failed")
            return 2

        rearm_config = RearmConfig(
            clear_reads=args.rearm_clear_reads,
            poll_seconds=args.rearm_poll_seconds,
            delay_seconds=args.rearm_delay_seconds,
        )
        rearm_config.validate()

        with RuntimeFileLock(args.lock_file):
            pipeline = RealDeviceDisposalPipeline(
                config=RealDevicePipelineConfig(
                    telemetry_mode=args.telemetry_mode,
                )
            )
            logger.info(
                "Continuous runtime started | telemetryMode=%s | lockFile=%s",
                args.telemetry_mode,
                Path(args.lock_file).expanduser(),
            )
            return run_continuous_sessions(
                pipeline=pipeline,
                rearm_waiter=lambda: wait_for_front_clear(config=rearm_config),
                result_emitter=lambda result: emit_event_result(
                    result,
                    json_lines=args.json,
                ),
            )
    except (KeyboardInterrupt, ShutdownRequested) as exc:
        logger.info("Continuous runtime stopped intentionally | reason=%s", exc)
        return 0
    except Exception:
        logger.exception("Continuous runtime failed during startup")
        return 2
    finally:
        _restore_signal_handlers(previous_handlers)


if __name__ == "__main__":
    sys.exit(main())

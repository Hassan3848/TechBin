"""Safe tests for the continuous real-device orchestrator without hardware."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.engine.real_device_pipeline import RealDeviceDisposalPipeline
from app.main_real_device_continuous import (
    RearmConfig,
    RuntimeFileLock,
    RuntimeLockError,
    ShutdownRequested,
    run_continuous_sessions,
    wait_for_front_clear,
)
from app.telemetry.totals import LocalTotalsStore


@dataclass(frozen=True)
class FakeResult:
    status: str
    processed: bool = False
    eventId: str | None = None
    faultCode: str | None = None
    message: str = "test"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "processed": self.processed,
            "eventId": self.eventId,
            "faultCode": self.faultCode,
            "message": self.message,
        }


class FakePipeline:
    def __init__(self, results: list[FakeResult | BaseException]) -> None:
        self.results = list(results)
        self.closed = False

    def process_once(self) -> FakeResult:
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    def close(self) -> None:
        self.closed = True


class DictResult:
    def __init__(self, data: dict) -> None:
        self.data = data

    def to_dict(self) -> dict:
        return self.data


class FakeSessionDetector:
    def __init__(self, readings: list[dict]) -> None:
        self.readings = list(readings)
        self.calls = 0

    def update(self) -> DictResult:
        reading = self.readings[self.calls]
        self.calls += 1
        return DictResult(reading)


class FakeStack:
    def __init__(self, readings: list[dict]) -> None:
        self.session_detector = FakeSessionDetector(readings)
        self.closed = False

    def close(self) -> None:
        self.closed = True


class CloseableBackend:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeMetalResource:
    def __init__(self) -> None:
        self.backend = CloseableBackend()


def front_reading(*, present: bool | None, valid: bool = True) -> dict:
    return {
        "valid": valid,
        "presenceDetected": present,
        "distanceCm": 20.0 if present else 80.0,
    }


def test_nonfatal_results_continue_until_fault() -> None:
    pipeline = FakePipeline(
        [
            FakeResult("uncertain_prediction"),
            FakeResult("side_unconfirmed", eventId="event-1"),
            FakeResult("processed", processed=True, eventId="event-2"),
            FakeResult("fault", faultCode="hardware_failed"),
        ]
    )
    emitted: list[str] = []
    rearm_calls: list[bool] = []

    exit_code = run_continuous_sessions(
        pipeline=pipeline,
        rearm_waiter=lambda: rearm_calls.append(True),
        result_emitter=lambda result: emitted.append(result.status),
    )

    assert exit_code == 1
    assert emitted == [
        "uncertain_prediction",
        "side_unconfirmed",
        "processed",
        "fault",
    ]
    assert len(rearm_calls) == 3
    assert pipeline.closed is True


def test_shutdown_is_clean_exit() -> None:
    pipeline = FakePipeline([ShutdownRequested(15)])

    exit_code = run_continuous_sessions(
        pipeline=pipeline,
        rearm_waiter=lambda: None,
        result_emitter=lambda result: None,
    )

    assert exit_code == 0
    assert pipeline.closed is True


def test_rearm_requires_consecutive_valid_clear_readings() -> None:
    stack = FakeStack(
        [
            front_reading(present=True),
            front_reading(present=False),
            front_reading(present=False),
            front_reading(present=None, valid=False),
            front_reading(present=False),
            front_reading(present=False),
            front_reading(present=False),
        ]
    )
    sleeps: list[float] = []

    wait_for_front_clear(
        config=RearmConfig(clear_reads=3, poll_seconds=0.1, delay_seconds=0.5),
        stack_factory=lambda: stack,
        sleep=sleeps.append,
    )

    assert stack.session_detector.calls == 7
    assert stack.closed is True
    assert sleeps == [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.5]


def test_rearm_failure_is_fatal() -> None:
    pipeline = FakePipeline([FakeResult("processed", processed=True)])

    def fail_rearm() -> None:
        raise RuntimeError("front sensor unavailable")

    exit_code = run_continuous_sessions(
        pipeline=pipeline,
        rearm_waiter=fail_rearm,
        result_emitter=lambda result: None,
    )

    assert exit_code == 1
    assert pipeline.closed is True


def test_runtime_lock_rejects_second_owner() -> None:
    with TemporaryDirectory(prefix="techbin_continuous_lock_") as tmpdir:
        lock_path = Path(tmpdir) / "runtime.lock"
        first = RuntimeFileLock(lock_path)
        second = RuntimeFileLock(lock_path)

        first.acquire()
        try:
            try:
                second.acquire()
            except RuntimeLockError:
                pass
            else:
                raise AssertionError("Second runtime unexpectedly acquired the lock")
        finally:
            first.release()

        second.acquire()
        second.release()


def test_pipeline_releases_and_resets_owned_session_hardware() -> None:
    with TemporaryDirectory(prefix="techbin_continuous_resources_") as tmpdir:
        pipeline = RealDeviceDisposalPipeline(
            totals_store=LocalTotalsStore(Path(tmpdir) / "totals.json")
        )
        stack = FakeStack([])
        metal_sensor = FakeMetalResource()
        pipeline.hardware_stack = stack
        pipeline.metal_sensor = metal_sensor

        pipeline._release_owned_session_hardware()

        assert stack.closed is True
        assert metal_sensor.backend.closed is True
        assert pipeline.hardware_stack is None
        assert pipeline.metal_sensor is None


def main() -> None:
    test_nonfatal_results_continue_until_fault()
    test_shutdown_is_clean_exit()
    test_rearm_requires_consecutive_valid_clear_readings()
    test_rearm_failure_is_fatal()
    test_runtime_lock_rejects_second_owner()
    test_pipeline_releases_and_resets_owned_session_hardware()
    print("All continuous real-device runtime tests passed.")


if __name__ == "__main__":
    main()

"""
TechBin fast Arduino side confirmation runner.

Purpose:
    Confirm left/right disposal side quickly enough for real-time user feedback.

Target:
    Final side confirmation should finish in about 1.0–1.5 seconds when one
    side is clearly detected.

Why:
    Audio feedback should happen while the user is still near the bin.

Flow:
    1. Capture baseline from Arduino left/right ultrasonic readings.
    2. Read side-detection samples for a short bounded window.
    3. Stop early if left/right becomes clearly dominant.
    4. Return confirmed side or reject as unknown/ambiguous.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from app.logger import get_logger
from app.sensors.arduino_bridge import ArduinoSerialBridge
from app.sensors.arduino_side_confirmation import (
    ArduinoSideConfirmationConfig,
    ArduinoSideConfirmationResult,
    ArduinoSideConfirmationWindow,
)
from app.sensors.arduino_side_detection_monitor import (
    ArduinoSideBaselineResult,
    ArduinoSideDetectionMonitor,
    ArduinoSideDetectionMonitorResult,
)
from app.sensors.side_detector import SideDetectionConfig


logger = get_logger(__name__)


FastDecisionReason = Literal[
    "early_confirmed",
    "timeout_decision",
    "max_samples_decision",
    "baseline_failed",
    "fault",
]


class FastArduinoSideConfirmationRunnerError(RuntimeError):
    """Raised when fast Arduino side confirmation fails."""


@dataclass(frozen=True)
class FastArduinoSideConfirmationConfig:
    """
    Fast confirmation settings.

    max_confirm_seconds:
        Maximum time allowed for one side-confirmation attempt.

    max_samples_per_window:
        Maximum samples allowed even if time remains.

    early_min_samples:
        Minimum samples before early confirmation is allowed.

    early_win_count:
        If one side reaches this count, it may be confirmed early.

    early_winner_ratio:
        Winning side must be this fraction of valid side detections.

    early_dominance_margin_count:
        Winning side count must exceed the other side by this amount.

    final_*:
        Rules used if early confirmation does not happen before timeout.
    """

    max_confirm_seconds: float = 1.4
    max_samples_per_window: int = 6
    sample_pause_seconds: float = 0.0

    early_min_samples: int = 3
    early_win_count: int = 3
    early_winner_ratio: float = 0.80
    early_dominance_margin_count: int = 2

    final_min_samples: int = 3
    final_min_valid_side_samples: int = 2
    final_winner_ratio: float = 0.65
    final_dominance_margin_count: int = 1

    keep_samples: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FastArduinoSideConfirmationResult:
    """
    Final fast side confirmation result.
    """

    timestamp: str
    confirmed: bool
    valid: bool
    confirmedSide: str
    disposalSide: str | None
    faultCode: str | None
    message: str
    reason: FastDecisionReason
    elapsedSeconds: float
    samplesCollected: int
    confirmation: dict[str, Any]
    baseline: dict[str, Any] | None
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _round_seconds(value: float) -> float:
    return round(float(value), 4)


def _read_ultrasonic_once_bounded(
    bridge: ArduinoSerialBridge,
    *,
    max_lines: int,
):
    try:
        return bridge.read_ultrasonic_once(max_lines=max_lines)
    except TypeError as exc:
        message = str(exc)
        if "max_lines" not in message and "positional" not in message:
            raise
        return bridge.read_ultrasonic_once()


class FastArduinoSideConfirmationRunner:
    """
    Production-style fast side confirmation runner.

    This class reads live Arduino data through ArduinoSerialBridge.
    """

    def __init__(
        self,
        *,
        side_monitor: ArduinoSideDetectionMonitor | None = None,
        config: FastArduinoSideConfirmationConfig | None = None,
    ) -> None:
        self.config = config or FastArduinoSideConfirmationConfig()

        self.side_monitor = side_monitor or ArduinoSideDetectionMonitor(
            config=SideDetectionConfig(
                disturbance_threshold_cm=5.0,
                dominance_margin_cm=6.0,
                use_absolute_delta=False,
            )
        )

        self._last_baseline: ArduinoSideBaselineResult | None = None

        self._validate_config()

    def _validate_config(self) -> None:
        if self.config.max_confirm_seconds <= 0:
            raise FastArduinoSideConfirmationRunnerError(
                "max_confirm_seconds must be positive"
            )

        if self.config.max_samples_per_window <= 0:
            raise FastArduinoSideConfirmationRunnerError(
                "max_samples_per_window must be positive"
            )

        if self.config.early_min_samples <= 0:
            raise FastArduinoSideConfirmationRunnerError(
                "early_min_samples must be positive"
            )

        if self.config.early_win_count <= 0:
            raise FastArduinoSideConfirmationRunnerError(
                "early_win_count must be positive"
            )

    def capture_baseline(
        self,
        bridge: ArduinoSerialBridge,
    ) -> ArduinoSideBaselineResult:
        """
        Capture side-detection baseline from Arduino.
        """

        arduino_reading = bridge.read_ultrasonic_once()
        baseline = self.side_monitor.capture_baseline_from_arduino_reading(
            arduino_reading
        )

        self._last_baseline = baseline

        return baseline

    def confirm_once(
        self,
        bridge: ArduinoSerialBridge,
    ) -> FastArduinoSideConfirmationResult:
        """
        Confirm side once using a fast time-bounded window.
        """

        started = time.monotonic()

        confirmation_config = ArduinoSideConfirmationConfig(
            min_samples=self.config.final_min_samples,
            min_valid_side_samples=self.config.final_min_valid_side_samples,
            winner_ratio=self.config.final_winner_ratio,
            dominance_margin_count=self.config.final_dominance_margin_count,
            reject_on_any_ambiguous=False,
        )

        window = ArduinoSideConfirmationWindow(
            config=confirmation_config,
            keep_samples=self.config.keep_samples,
        )

        try:
            while True:
                elapsed = time.monotonic() - started

                if elapsed >= self.config.max_confirm_seconds:
                    decision = window.decide()
                    return self._build_result(
                        decision=decision,
                        reason="timeout_decision",
                        elapsed_seconds=elapsed,
                    )

                if window.sample_count >= self.config.max_samples_per_window:
                    decision = window.decide()
                    return self._build_result(
                        decision=decision,
                        reason="max_samples_decision",
                        elapsed_seconds=elapsed,
                    )

                arduino_reading = _read_ultrasonic_once_bounded(
                    bridge,
                    max_lines=1,
                )
                side_result = self.side_monitor.detect_from_arduino_reading(
                    arduino_reading
                )
                window.add_sample(side_result)

                early_decision = window.decide()

                if self._is_early_confirmable(early_decision):
                    elapsed = time.monotonic() - started

                    logger.info(
                        "Fast Arduino side confirmed early | side=%s | samples=%s | elapsed=%.3f",
                        early_decision.confirmedSide,
                        early_decision.totalSamples,
                        elapsed,
                    )

                    return self._build_result(
                        decision=early_decision,
                        reason="early_confirmed",
                        elapsed_seconds=elapsed,
                    )

                if self.config.sample_pause_seconds > 0:
                    time.sleep(self.config.sample_pause_seconds)

        except Exception as exc:
            elapsed = time.monotonic() - started
            logger.exception("Fast Arduino side confirmation failed")

            empty_decision = ArduinoSideConfirmationResult(
                timestamp=_now_iso(),
                confirmed=False,
                valid=False,
                confirmedSide="unknown",
                disposalSide=None,
                faultCode="fast_arduino_side_confirmation_failed",
                message=str(exc),
                totalSamples=window.sample_count,
                validSideSamples=0,
                leftCount=0,
                rightCount=0,
                unknownCount=0,
                ambiguousCount=0,
                faultCount=1,
                leftRatio=0.0,
                rightRatio=0.0,
                winningRatio=0.0,
                dominanceMargin=0,
                config=confirmation_config.to_dict(),
                samples=[],
            )

            return self._build_result(
                decision=empty_decision,
                reason="fault",
                elapsed_seconds=elapsed,
            )

    def _is_early_confirmable(
        self,
        decision: ArduinoSideConfirmationResult,
    ) -> bool:
        if not decision.valid:
            return False

        if decision.confirmedSide not in ("left", "right"):
            return False

        if decision.totalSamples < self.config.early_min_samples:
            return False

        if decision.confirmedSide == "left":
            winner_count = decision.leftCount
            loser_count = decision.rightCount
        else:
            winner_count = decision.rightCount
            loser_count = decision.leftCount

        if winner_count < self.config.early_win_count:
            return False

        if decision.winningRatio < self.config.early_winner_ratio:
            return False

        if winner_count - loser_count < self.config.early_dominance_margin_count:
            return False

        return True

    def _build_result(
        self,
        *,
        decision: ArduinoSideConfirmationResult,
        reason: FastDecisionReason,
        elapsed_seconds: float,
    ) -> FastArduinoSideConfirmationResult:
        return FastArduinoSideConfirmationResult(
            timestamp=_now_iso(),
            confirmed=decision.confirmed,
            valid=decision.valid,
            confirmedSide=decision.confirmedSide,
            disposalSide=decision.disposalSide,
            faultCode=decision.faultCode,
            message=decision.message,
            reason=reason,
            elapsedSeconds=_round_seconds(elapsed_seconds),
            samplesCollected=decision.totalSamples,
            confirmation=decision.to_dict(),
            baseline=(
                self._last_baseline.to_dict()
                if self._last_baseline is not None
                else None
            ),
            config=self.config.to_dict(),
        )


__all__ = [
    "FastDecisionReason",
    "FastArduinoSideConfirmationRunnerError",
    "FastArduinoSideConfirmationConfig",
    "FastArduinoSideConfirmationResult",
    "FastArduinoSideConfirmationRunner",
]

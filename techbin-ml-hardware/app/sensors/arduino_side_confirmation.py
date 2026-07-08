"""
TechBin Arduino side confirmation window.

Purpose:
    Stabilize Arduino-backed side detection before using it in a disposal event.

Why this exists:
    A single ultrasonic side reading can be noisy during fast movement.
    Production event decisions should use a short confirmation window.

Example:
    10 samples collected:
        left = 7
        right = 1
        unknown = 2

    final confirmed side = left

This module does not read Arduino directly.
It only aggregates results produced by ArduinoSideDetectionMonitor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.logger import get_logger
from app.sensors.arduino_side_detection_monitor import (
    ArduinoSideDetectionMonitorResult,
)


logger = get_logger(__name__)


ConfirmedSide = Literal["left", "right", "unknown", "ambiguous"]


class ArduinoSideConfirmationError(RuntimeError):
    """Raised when side confirmation fails unexpectedly."""


@dataclass(frozen=True)
class ArduinoSideConfirmationConfig:
    """
    Configuration for side confirmation.

    min_samples:
        Minimum total samples required before making a decision.

    min_valid_side_samples:
        Minimum valid left/right detections required.

    winner_ratio:
        Winning side must be at least this fraction of valid left/right detections.

    dominance_margin_count:
        Winning side count must exceed the other side by this many samples.

    reject_on_any_ambiguous:
        If True, any ambiguous sample can make the final result stricter.
        For now default is False because open-air testing can create occasional noise.
    """

    min_samples: int = 5
    min_valid_side_samples: int = 3
    winner_ratio: float = 0.65
    dominance_margin_count: int = 2
    reject_on_any_ambiguous: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArduinoSideConfirmationResult:
    """
    Final confirmation result after a window of side detections.
    """

    timestamp: str
    confirmed: bool
    valid: bool
    confirmedSide: ConfirmedSide
    disposalSide: str | None
    faultCode: str | None
    message: str

    totalSamples: int
    validSideSamples: int
    leftCount: int
    rightCount: int
    unknownCount: int
    ambiguousCount: int
    faultCount: int

    leftRatio: float
    rightRatio: float
    winningRatio: float
    dominanceMargin: int

    config: dict[str, Any]
    samples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _round_ratio(value: float) -> float:
    return round(float(value), 4)


class ArduinoSideConfirmationWindow:
    """
    Aggregates Arduino side detection results and produces one stable decision.
    """

    def __init__(
        self,
        *,
        config: ArduinoSideConfirmationConfig | None = None,
        keep_samples: bool = True,
    ) -> None:
        self.config = config or ArduinoSideConfirmationConfig()
        self.keep_samples = keep_samples
        self._samples: list[ArduinoSideDetectionMonitorResult] = []

        self._validate_config()

    def _validate_config(self) -> None:
        if self.config.min_samples <= 0:
            raise ArduinoSideConfirmationError("min_samples must be greater than zero")

        if self.config.min_valid_side_samples <= 0:
            raise ArduinoSideConfirmationError(
                "min_valid_side_samples must be greater than zero"
            )

        if not 0.0 < self.config.winner_ratio <= 1.0:
            raise ArduinoSideConfirmationError(
                "winner_ratio must be greater than 0 and less than or equal to 1"
            )

        if self.config.dominance_margin_count < 0:
            raise ArduinoSideConfirmationError(
                "dominance_margin_count cannot be negative"
            )

    def reset(self) -> None:
        self._samples.clear()

    def add_sample(self, result: ArduinoSideDetectionMonitorResult) -> None:
        self._samples.append(result)

    def add_samples(
        self,
        results: list[ArduinoSideDetectionMonitorResult],
    ) -> None:
        for result in results:
            self.add_sample(result)

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def decide(self) -> ArduinoSideConfirmationResult:
        """
        Decide final side from collected samples.
        """

        total_samples = len(self._samples)

        left_count = 0
        right_count = 0
        unknown_count = 0
        ambiguous_count = 0
        fault_count = 0

        sample_dicts: list[dict[str, Any]] = []

        for sample in self._samples:
            if self.keep_samples:
                sample_dicts.append(sample.to_dict())

            detected_side = sample.detectedSide

            if detected_side == "left" and sample.valid:
                left_count += 1
            elif detected_side == "right" and sample.valid:
                right_count += 1
            elif detected_side == "ambiguous":
                ambiguous_count += 1
            elif detected_side == "unknown":
                unknown_count += 1
            else:
                fault_count += 1

            if sample.faultCode and sample.faultCode not in (
                "no_compartment_disturbance",
                "ambiguous_compartment_disturbance",
            ):
                fault_count += 1

        valid_side_samples = left_count + right_count

        left_ratio = (
            left_count / valid_side_samples
            if valid_side_samples > 0
            else 0.0
        )

        right_ratio = (
            right_count / valid_side_samples
            if valid_side_samples > 0
            else 0.0
        )

        if left_count > right_count:
            winner: ConfirmedSide = "left"
            winner_count = left_count
            loser_count = right_count
            winning_ratio = left_ratio
        elif right_count > left_count:
            winner = "right"
            winner_count = right_count
            loser_count = left_count
            winning_ratio = right_ratio
        else:
            winner = "ambiguous" if valid_side_samples > 0 else "unknown"
            winner_count = left_count
            loser_count = right_count
            winning_ratio = 0.0

        dominance_margin = winner_count - loser_count

        if total_samples < self.config.min_samples:
            return self._build_result(
                confirmed=False,
                valid=False,
                confirmed_side="unknown",
                disposal_side=None,
                fault_code="insufficient_samples",
                message=(
                    f"Only {total_samples} samples collected; "
                    f"minimum required is {self.config.min_samples}."
                ),
                total_samples=total_samples,
                valid_side_samples=valid_side_samples,
                left_count=left_count,
                right_count=right_count,
                unknown_count=unknown_count,
                ambiguous_count=ambiguous_count,
                fault_count=fault_count,
                left_ratio=left_ratio,
                right_ratio=right_ratio,
                winning_ratio=winning_ratio,
                dominance_margin=dominance_margin,
                sample_dicts=sample_dicts,
            )

        if valid_side_samples < self.config.min_valid_side_samples:
            return self._build_result(
                confirmed=False,
                valid=False,
                confirmed_side="unknown",
                disposal_side=None,
                fault_code="insufficient_valid_side_samples",
                message=(
                    f"Only {valid_side_samples} valid left/right detections; "
                    f"minimum required is {self.config.min_valid_side_samples}."
                ),
                total_samples=total_samples,
                valid_side_samples=valid_side_samples,
                left_count=left_count,
                right_count=right_count,
                unknown_count=unknown_count,
                ambiguous_count=ambiguous_count,
                fault_count=fault_count,
                left_ratio=left_ratio,
                right_ratio=right_ratio,
                winning_ratio=winning_ratio,
                dominance_margin=dominance_margin,
                sample_dicts=sample_dicts,
            )

        if self.config.reject_on_any_ambiguous and ambiguous_count > 0:
            return self._build_result(
                confirmed=False,
                valid=False,
                confirmed_side="ambiguous",
                disposal_side=None,
                fault_code="ambiguous_sample_present",
                message="At least one ambiguous sample was present in confirmation window.",
                total_samples=total_samples,
                valid_side_samples=valid_side_samples,
                left_count=left_count,
                right_count=right_count,
                unknown_count=unknown_count,
                ambiguous_count=ambiguous_count,
                fault_count=fault_count,
                left_ratio=left_ratio,
                right_ratio=right_ratio,
                winning_ratio=winning_ratio,
                dominance_margin=dominance_margin,
                sample_dicts=sample_dicts,
            )

        if winner not in ("left", "right"):
            return self._build_result(
                confirmed=False,
                valid=False,
                confirmed_side=winner,
                disposal_side=None,
                fault_code="no_dominant_side",
                message="No dominant left/right side was found.",
                total_samples=total_samples,
                valid_side_samples=valid_side_samples,
                left_count=left_count,
                right_count=right_count,
                unknown_count=unknown_count,
                ambiguous_count=ambiguous_count,
                fault_count=fault_count,
                left_ratio=left_ratio,
                right_ratio=right_ratio,
                winning_ratio=winning_ratio,
                dominance_margin=dominance_margin,
                sample_dicts=sample_dicts,
            )

        if winning_ratio < self.config.winner_ratio:
            return self._build_result(
                confirmed=False,
                valid=False,
                confirmed_side="ambiguous",
                disposal_side=None,
                fault_code="winner_ratio_too_low",
                message=(
                    f"Winning ratio {winning_ratio:.2f} is below required "
                    f"{self.config.winner_ratio:.2f}."
                ),
                total_samples=total_samples,
                valid_side_samples=valid_side_samples,
                left_count=left_count,
                right_count=right_count,
                unknown_count=unknown_count,
                ambiguous_count=ambiguous_count,
                fault_count=fault_count,
                left_ratio=left_ratio,
                right_ratio=right_ratio,
                winning_ratio=winning_ratio,
                dominance_margin=dominance_margin,
                sample_dicts=sample_dicts,
            )

        if dominance_margin < self.config.dominance_margin_count:
            return self._build_result(
                confirmed=False,
                valid=False,
                confirmed_side="ambiguous",
                disposal_side=None,
                fault_code="dominance_margin_too_low",
                message=(
                    f"Dominance margin {dominance_margin} is below required "
                    f"{self.config.dominance_margin_count}."
                ),
                total_samples=total_samples,
                valid_side_samples=valid_side_samples,
                left_count=left_count,
                right_count=right_count,
                unknown_count=unknown_count,
                ambiguous_count=ambiguous_count,
                fault_count=fault_count,
                left_ratio=left_ratio,
                right_ratio=right_ratio,
                winning_ratio=winning_ratio,
                dominance_margin=dominance_margin,
                sample_dicts=sample_dicts,
            )

        logger.info(
            "Arduino side confirmed | side=%s | left=%s | right=%s | unknown=%s | ambiguous=%s",
            winner,
            left_count,
            right_count,
            unknown_count,
            ambiguous_count,
        )

        return self._build_result(
            confirmed=True,
            valid=True,
            confirmed_side=winner,
            disposal_side=winner,
            fault_code=None,
            message=f"Arduino side confirmation accepted: {winner}.",
            total_samples=total_samples,
            valid_side_samples=valid_side_samples,
            left_count=left_count,
            right_count=right_count,
            unknown_count=unknown_count,
            ambiguous_count=ambiguous_count,
            fault_count=fault_count,
            left_ratio=left_ratio,
            right_ratio=right_ratio,
            winning_ratio=winning_ratio,
            dominance_margin=dominance_margin,
            sample_dicts=sample_dicts,
        )

    def _build_result(
        self,
        *,
        confirmed: bool,
        valid: bool,
        confirmed_side: ConfirmedSide,
        disposal_side: str | None,
        fault_code: str | None,
        message: str,
        total_samples: int,
        valid_side_samples: int,
        left_count: int,
        right_count: int,
        unknown_count: int,
        ambiguous_count: int,
        fault_count: int,
        left_ratio: float,
        right_ratio: float,
        winning_ratio: float,
        dominance_margin: int,
        sample_dicts: list[dict[str, Any]],
    ) -> ArduinoSideConfirmationResult:
        return ArduinoSideConfirmationResult(
            timestamp=_now_iso(),
            confirmed=confirmed,
            valid=valid,
            confirmedSide=confirmed_side,
            disposalSide=disposal_side,
            faultCode=fault_code,
            message=message,
            totalSamples=total_samples,
            validSideSamples=valid_side_samples,
            leftCount=left_count,
            rightCount=right_count,
            unknownCount=unknown_count,
            ambiguousCount=ambiguous_count,
            faultCount=fault_count,
            leftRatio=_round_ratio(left_ratio),
            rightRatio=_round_ratio(right_ratio),
            winningRatio=_round_ratio(winning_ratio),
            dominanceMargin=dominance_margin,
            config=self.config.to_dict(),
            samples=sample_dicts,
        )


def confirm_arduino_side_results(
    results: list[ArduinoSideDetectionMonitorResult],
    *,
    config: ArduinoSideConfirmationConfig | None = None,
    keep_samples: bool = True,
) -> ArduinoSideConfirmationResult:
    """
    Convenience function for confirming a list of side detection results.
    """

    window = ArduinoSideConfirmationWindow(
        config=config,
        keep_samples=keep_samples,
    )
    window.add_samples(results)
    return window.decide()


__all__ = [
    "ConfirmedSide",
    "ArduinoSideConfirmationError",
    "ArduinoSideConfirmationConfig",
    "ArduinoSideConfirmationResult",
    "ArduinoSideConfirmationWindow",
    "confirm_arduino_side_results",
]

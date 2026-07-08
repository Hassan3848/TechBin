"""
TechBin Arduino side detection monitor.

Purpose:
    Use Arduino-provided left/right ultrasonic readings to detect which
    compartment was disturbed during a disposal session.

Architecture:
    Arduino Uno:
        left HC-SR04  -> D7/D8
        right HC-SR04 -> D9/D10
        sends filtered readings to Raspberry Pi over USB Serial

    Raspberry Pi:
        captures baseline reading before disposal
        captures current reading during/after disposal
        compares distance changes
        detects disposal side: left/right/unknown/ambiguous

Important:
    This module does not replace ML classification.
    It only provides compartment-side evidence.

Final product logic:
    left compartment  -> non-recyclable/trash
    right compartment -> recyclable
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from app.logger import get_logger
from app.sensors.arduino_bridge import ArduinoUltrasonicReading
from app.sensors.arduino_ultrasonic_adapter import (
    ArduinoUltrasonicPair,
    arduino_reading_to_ultrasonic_pair,
)
from app.sensors.side_detector import (
    SideDetectionConfig,
    SideDetectionResult,
    detect_side_from_readings,
)


logger = get_logger(__name__)


class ArduinoSideDetectionMonitorError(RuntimeError):
    """Raised when Arduino side detection monitoring fails."""


@dataclass(frozen=True)
class ArduinoSideBaselineResult:
    """
    Result of capturing a left/right side-detection baseline.
    """

    timestamp: str
    baselineCaptured: bool
    valid: bool
    faultCodes: list[str]
    message: str
    baselinePair: dict[str, Any] | None
    arduinoSequence: int | None
    arduinoMillis: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArduinoSideDetectionMonitorResult:
    """
    Result of side detection using Arduino ultrasonic readings.
    """

    timestamp: str
    valid: bool
    detectedSide: str
    disposalSide: str | None
    faultCode: str | None
    message: str
    sideDetection: dict[str, Any] | None
    baselinePair: dict[str, Any] | None
    currentPair: dict[str, Any] | None
    baselineSequence: int | None
    currentSequence: int | None
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _pair_faults(pair: ArduinoUltrasonicPair) -> list[str]:
    faults: list[str] = []

    if not pair.left.valid:
        faults.append(f"left:{pair.left.faultCode or 'invalid'}")

    if not pair.right.valid:
        faults.append(f"right:{pair.right.faultCode or 'invalid'}")

    return faults


class ArduinoSideDetectionMonitor:
    """
    Stateful Arduino-backed side detection monitor.

    Usage:
        monitor = ArduinoSideDetectionMonitor()
        monitor.capture_baseline_from_arduino_reading(reading_before_disposal)
        result = monitor.detect_from_arduino_reading(reading_after_disposal)
    """

    def __init__(
        self,
        *,
        config: SideDetectionConfig | None = None,
    ) -> None:
        self.config = config or SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
            use_absolute_delta=False,
        )

        self._baseline_pair: ArduinoUltrasonicPair | None = None

    @property
    def baseline_pair(self) -> ArduinoUltrasonicPair | None:
        return self._baseline_pair

    def clear_baseline(self) -> None:
        """
        Clear stored baseline.
        """

        self._baseline_pair = None

    def capture_baseline_pair(
        self,
        pair: ArduinoUltrasonicPair,
    ) -> ArduinoSideBaselineResult:
        """
        Capture baseline from an already-adapted Arduino ultrasonic pair.
        """

        faults = _pair_faults(pair)

        if faults:
            return ArduinoSideBaselineResult(
                timestamp=_now_iso(),
                baselineCaptured=False,
                valid=False,
                faultCodes=faults,
                message="Baseline was not captured because one or both Arduino readings are invalid.",
                baselinePair=pair.to_dict(),
                arduinoSequence=pair.arduinoSequence,
                arduinoMillis=pair.arduinoMillis,
            )

        self._baseline_pair = pair

        logger.info(
            "Arduino side baseline captured | seq=%s | left=%s | right=%s",
            pair.arduinoSequence,
            pair.left.distanceCm,
            pair.right.distanceCm,
        )

        return ArduinoSideBaselineResult(
            timestamp=_now_iso(),
            baselineCaptured=True,
            valid=True,
            faultCodes=[],
            message="Arduino side baseline captured successfully.",
            baselinePair=pair.to_dict(),
            arduinoSequence=pair.arduinoSequence,
            arduinoMillis=pair.arduinoMillis,
        )

    def capture_baseline_from_arduino_reading(
        self,
        arduino_reading: ArduinoUltrasonicReading,
    ) -> ArduinoSideBaselineResult:
        """
        Convert Arduino reading and capture baseline.
        """

        pair = arduino_reading_to_ultrasonic_pair(arduino_reading)
        return self.capture_baseline_pair(pair)

    def detect_from_pair(
        self,
        current_pair: ArduinoUltrasonicPair,
    ) -> ArduinoSideDetectionMonitorResult:
        """
        Detect disposal side from current Arduino pair and stored baseline.
        """

        if self._baseline_pair is None:
            return ArduinoSideDetectionMonitorResult(
                timestamp=_now_iso(),
                valid=False,
                detectedSide="unknown",
                disposalSide=None,
                faultCode="arduino_side_baseline_missing",
                message="Cannot detect side because baseline has not been captured.",
                sideDetection=None,
                baselinePair=None,
                currentPair=current_pair.to_dict(),
                baselineSequence=None,
                currentSequence=current_pair.arduinoSequence,
                config=self.config.to_dict(),
            )

        current_faults = _pair_faults(current_pair)

        if current_faults:
            return ArduinoSideDetectionMonitorResult(
                timestamp=_now_iso(),
                valid=False,
                detectedSide="unknown",
                disposalSide=None,
                faultCode="arduino_current_pair_invalid",
                message="Cannot detect side because current Arduino readings are invalid.",
                sideDetection=None,
                baselinePair=self._baseline_pair.to_dict(),
                currentPair=current_pair.to_dict(),
                baselineSequence=self._baseline_pair.arduinoSequence,
                currentSequence=current_pair.arduinoSequence,
                config=self.config.to_dict(),
            )

        side_result: SideDetectionResult = detect_side_from_readings(
            left_baseline=self._baseline_pair.left,
            left_current=current_pair.left,
            right_baseline=self._baseline_pair.right,
            right_current=current_pair.right,
            config=self.config,
        )

        logger.info(
            "Arduino side detection | detected=%s | valid=%s | fault=%s",
            side_result.detectedSide,
            side_result.valid,
            side_result.faultCode,
        )

        return ArduinoSideDetectionMonitorResult(
            timestamp=_now_iso(),
            valid=side_result.valid,
            detectedSide=side_result.detectedSide,
            disposalSide=side_result.disposalSide,
            faultCode=side_result.faultCode,
            message=side_result.message,
            sideDetection=side_result.to_dict(),
            baselinePair=self._baseline_pair.to_dict(),
            currentPair=current_pair.to_dict(),
            baselineSequence=self._baseline_pair.arduinoSequence,
            currentSequence=current_pair.arduinoSequence,
            config=self.config.to_dict(),
        )

    def detect_from_arduino_reading(
        self,
        arduino_reading: ArduinoUltrasonicReading,
    ) -> ArduinoSideDetectionMonitorResult:
        """
        Convert Arduino reading and detect side.
        """

        current_pair = arduino_reading_to_ultrasonic_pair(arduino_reading)
        return self.detect_from_pair(current_pair)


__all__ = [
    "ArduinoSideDetectionMonitorError",
    "ArduinoSideBaselineResult",
    "ArduinoSideDetectionMonitorResult",
    "ArduinoSideDetectionMonitor",
]

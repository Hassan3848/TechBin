"""
TechBin Arduino capacity monitor.

Purpose:
    Use Arduino-provided left/right ultrasonic readings to estimate
    compartment fill levels.

Architecture:
    Arduino Uno:
        reads left/right HC-SR04 sensors
        sends JSON to Raspberry Pi over USB Serial

    Raspberry Pi:
        reads Arduino JSON
        converts Arduino values to UltrasonicReading
        estimates fill percentage and capacity level

Traffic light meaning:
    green  -> low fill / enough space
    yellow -> half / medium fill
    red    -> full / high fill

Important:
    This module only decides capacity status.
    It does not directly control traffic light GPIO yet.
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
from app.sensors.fill_level import (
    FillLevelConfig,
    FillLevelResult,
    estimate_fill_level_from_ultrasonic,
)
from app.sensors.capacity_calibration import (
    techbin_left_fill_config,
    techbin_right_fill_config,
)


logger = get_logger(__name__)


class ArduinoCapacityMonitorError(RuntimeError):
    """Raised when Arduino capacity monitoring fails."""


@dataclass(frozen=True)
class ArduinoCompartmentCapacity:
    """
    Capacity result for one Arduino-backed compartment.
    """

    compartmentName: str
    timestamp: str
    distanceCm: float | None
    fillPercentage: float | None
    capacityLevel: str
    indicatorColor: str
    valid: bool
    faultCode: str | None
    message: str
    ultrasonicReading: dict[str, Any]
    fillLevel: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArduinoDualCapacityResult:
    """
    Capacity result for both left and right compartments.
    """

    timestamp: str
    left: dict[str, Any]
    right: dict[str, Any]
    overallValid: bool
    faultCodes: list[str]
    arduinoSequence: int | None
    arduinoMillis: int | None
    rawArduinoReading: dict[str, Any]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _compartment_capacity_from_fill_result(
    *,
    compartment_name: str,
    fill_result: FillLevelResult,
) -> ArduinoCompartmentCapacity:
    """
    Convert FillLevelResult into compact Arduino capacity structure.
    """

    return ArduinoCompartmentCapacity(
        compartmentName=compartment_name,
        timestamp=_now_iso(),
        distanceCm=fill_result.distanceCm,
        fillPercentage=fill_result.fillPercentage,
        capacityLevel=fill_result.capacityLevel,
        indicatorColor=fill_result.indicatorColor,
        valid=fill_result.valid,
        faultCode=fill_result.faultCode,
        message=fill_result.message,
        ultrasonicReading=fill_result.sourceReading or {},
        fillLevel=fill_result.to_dict(),
    )


class ArduinoCapacityMonitor:
    """
    Estimate left/right compartment capacity from Arduino ultrasonic readings.
    """

    def __init__(
        self,
        *,
        left_fill_config: FillLevelConfig | None = None,
        right_fill_config: FillLevelConfig | None = None,
    ) -> None:
        self.left_fill_config = left_fill_config or techbin_left_fill_config()
        self.right_fill_config = right_fill_config or techbin_right_fill_config()

    def evaluate_pair(
        self,
        pair: ArduinoUltrasonicPair,
    ) -> ArduinoDualCapacityResult:
        """
        Estimate capacity from already-adapted left/right ultrasonic pair.
        """

        left_fill = estimate_fill_level_from_ultrasonic(
            reading=pair.left,
            config=self.left_fill_config,
        )

        right_fill = estimate_fill_level_from_ultrasonic(
            reading=pair.right,
            config=self.right_fill_config,
        )

        left_capacity = _compartment_capacity_from_fill_result(
            compartment_name="left_compartment",
            fill_result=left_fill,
        )

        right_capacity = _compartment_capacity_from_fill_result(
            compartment_name="right_compartment",
            fill_result=right_fill,
        )

        fault_codes: list[str] = []

        if left_capacity.faultCode:
            fault_codes.append(f"left:{left_capacity.faultCode}")

        if right_capacity.faultCode:
            fault_codes.append(f"right:{right_capacity.faultCode}")

        overall_valid = left_capacity.valid and right_capacity.valid

        if overall_valid:
            message = "Arduino capacity monitor completed successfully."
        else:
            message = "Arduino capacity monitor completed with one or more faults."

        result = ArduinoDualCapacityResult(
            timestamp=_now_iso(),
            left=left_capacity.to_dict(),
            right=right_capacity.to_dict(),
            overallValid=overall_valid,
            faultCodes=fault_codes,
            arduinoSequence=pair.arduinoSequence,
            arduinoMillis=pair.arduinoMillis,
            rawArduinoReading=pair.rawArduinoReading,
            message=message,
        )

        logger.info(
            "Arduino capacity | left=%s/%s | right=%s/%s | valid=%s",
            left_capacity.fillPercentage,
            left_capacity.indicatorColor,
            right_capacity.fillPercentage,
            right_capacity.indicatorColor,
            overall_valid,
        )

        return result

    def evaluate_arduino_reading(
        self,
        arduino_reading: ArduinoUltrasonicReading,
    ) -> ArduinoDualCapacityResult:
        """
        Convert Arduino reading and estimate left/right capacity.
        """

        pair = arduino_reading_to_ultrasonic_pair(arduino_reading)
        return self.evaluate_pair(pair)


__all__ = [
    "ArduinoCapacityMonitorError",
    "ArduinoCompartmentCapacity",
    "ArduinoDualCapacityResult",
    "ArduinoCapacityMonitor",
]

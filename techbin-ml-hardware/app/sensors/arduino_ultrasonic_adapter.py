"""
TechBin Arduino ultrasonic adapter.

Purpose:
    Convert Arduino left/right ultrasonic readings into the same internal
    UltrasonicReading format used by the existing TechBin sensor modules.

Why this exists:
    The Arduino Uno now handles left/right HC-SR04 timing and filtering.
    Raspberry Pi receives clean values over USB Serial.

    Instead of rewriting fill-level and side-detection logic, we adapt Arduino
    readings into UltrasonicReading objects.

Architecture:
    Arduino:
        left HC-SR04  -> D7/D8
        right HC-SR04 -> D9/D10

    Raspberry Pi:
        reads Arduino JSON
        converts to UltrasonicReading
        uses existing fill_level.py and side_detector.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from app.sensors.arduino_bridge import ArduinoUltrasonicReading
from app.sensors.ultrasonic import UltrasonicReading


ArduinoSide = Literal["left", "right"]


class ArduinoUltrasonicAdapterError(RuntimeError):
    """Raised when Arduino ultrasonic data cannot be adapted."""


@dataclass(frozen=True)
class ArduinoUltrasonicPair:
    """
    Left/right UltrasonicReading pair adapted from one Arduino reading.
    """

    timestamp: str
    left: UltrasonicReading
    right: UltrasonicReading
    source: str
    arduinoSequence: int | None
    arduinoMillis: int | None
    rawArduinoReading: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "source": self.source,
            "arduinoSequence": self.arduinoSequence,
            "arduinoMillis": self.arduinoMillis,
            "rawArduinoReading": self.rawArduinoReading,
        }


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _fault_code_for_side(side: ArduinoSide, fault: str | None) -> str:
    clean_fault = (fault or "unknown").strip() or "unknown"
    return f"arduino_{side}_ultrasonic_{clean_fault}"


def _message_for_side(
    *,
    side: ArduinoSide,
    ok: bool,
    distance_cm: float | None,
    fault: str | None,
) -> str:
    if ok and distance_cm is not None:
        return f"Arduino {side} ultrasonic reading is valid."

    return (
        f"Arduino {side} ultrasonic reading is invalid. "
        f"fault={fault or 'unknown'}"
    )


def arduino_side_to_ultrasonic_reading(
    arduino_reading: ArduinoUltrasonicReading,
    *,
    side: ArduinoSide,
) -> UltrasonicReading:
    """
    Convert one Arduino side reading into UltrasonicReading.

    Note:
        triggerGpio and echoGpio fields are reused to store Arduino digital
        pin numbers for this Arduino-backed reading.

        left:
            triggerGpio = 7
            echoGpio = 8

        right:
            triggerGpio = 9
            echoGpio = 10
    """

    if side == "left":
        sensor_name = "left_ultrasonic"
        role = "left_compartment_detection_and_fill"
        distance_cm = arduino_reading.leftCm
        ok = arduino_reading.leftOk
        fault = arduino_reading.leftFault
        trigger_pin = 7
        echo_pin = 8

    elif side == "right":
        sensor_name = "right_ultrasonic"
        role = "right_compartment_detection_and_fill"
        distance_cm = arduino_reading.rightCm
        ok = arduino_reading.rightOk
        fault = arduino_reading.rightFault
        trigger_pin = 9
        echo_pin = 10

    else:
        raise ArduinoUltrasonicAdapterError(f"Unsupported Arduino side: {side}")

    valid = bool(ok and distance_cm is not None)

    if valid:
        rounded_distance = round(float(distance_cm), 2)

        return UltrasonicReading(
            sensorName=sensor_name,
            role=role,
            timestamp=arduino_reading.timestamp,
            distanceCm=rounded_distance,
            rawReadingsCm=[rounded_distance],
            valid=True,
            faultCode=None,
            message=_message_for_side(
                side=side,
                ok=True,
                distance_cm=rounded_distance,
                fault=fault,
            ),
            triggerGpio=trigger_pin,
            echoGpio=echo_pin,
        )

    return UltrasonicReading(
        sensorName=sensor_name,
        role=role,
        timestamp=arduino_reading.timestamp,
        distanceCm=None,
        rawReadingsCm=[],
        valid=False,
        faultCode=_fault_code_for_side(side, fault),
        message=_message_for_side(
            side=side,
            ok=False,
            distance_cm=distance_cm,
            fault=fault,
        ),
        triggerGpio=trigger_pin,
        echoGpio=echo_pin,
    )


def arduino_reading_to_ultrasonic_pair(
    arduino_reading: ArduinoUltrasonicReading,
) -> ArduinoUltrasonicPair:
    """
    Convert one Arduino reading into left/right UltrasonicReading pair.
    """

    left = arduino_side_to_ultrasonic_reading(
        arduino_reading,
        side="left",
    )

    right = arduino_side_to_ultrasonic_reading(
        arduino_reading,
        side="right",
    )

    return ArduinoUltrasonicPair(
        timestamp=_now_iso(),
        left=left,
        right=right,
        source="arduino_uno",
        arduinoSequence=arduino_reading.sequence,
        arduinoMillis=arduino_reading.arduinoMillis,
        rawArduinoReading=arduino_reading.to_dict(),
    )


def arduino_pair_to_dict(pair: ArduinoUltrasonicPair) -> dict[str, Any]:
    """
    Convenience helper for logging/debugging.
    """

    return asdict(pair)


__all__ = [
    "ArduinoSide",
    "ArduinoUltrasonicAdapterError",
    "ArduinoUltrasonicPair",
    "arduino_side_to_ultrasonic_reading",
    "arduino_reading_to_ultrasonic_pair",
    "arduino_pair_to_dict",
]

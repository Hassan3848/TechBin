"""
Test TechBin Arduino ultrasonic adapter.

This test does not touch real Arduino, GPIO, or serial ports.

Run:
    PYTHONPATH=. python3 tests/test_arduino_ultrasonic_adapter.py
"""

from __future__ import annotations

from pprint import pprint

from app.sensors.arduino_bridge import parse_arduino_ultrasonic_payload
from app.sensors.arduino_ultrasonic_adapter import (
    arduino_reading_to_ultrasonic_pair,
    arduino_side_to_ultrasonic_reading,
)
from app.sensors.fill_level import FillLevelConfig, estimate_fill_level_from_ultrasonic
from app.sensors.side_detector import SideDetectionConfig, detect_side_from_readings
from app.sensors.ultrasonic import UltrasonicReading


def make_baseline_reading(
    *,
    sensor_name: str,
    role: str,
    distance_cm: float,
    trigger_gpio: int,
    echo_gpio: int,
) -> UltrasonicReading:
    return UltrasonicReading(
        sensorName=sensor_name,
        role=role,
        timestamp="2026-01-01T00:00:00.000000",
        distanceCm=distance_cm,
        rawReadingsCm=[distance_cm],
        valid=True,
        faultCode=None,
        message="test baseline",
        triggerGpio=trigger_gpio,
        echoGpio=echo_gpio,
    )


def test_parse_and_adapt_valid_pair() -> None:
    print()
    print("========== Arduino Adapter: Valid Pair ==========")

    payload = {
        "type": "ultrasonic",
        "seq": 12,
        "ms": 3456,
        "left_cm": 44.16,
        "right_cm": 38.75,
        "left_ok": True,
        "right_ok": True,
        "left_fault": "none",
        "right_fault": "none",
    }

    arduino_reading = parse_arduino_ultrasonic_payload(payload)
    pair = arduino_reading_to_ultrasonic_pair(arduino_reading)

    pprint(pair.to_dict())

    assert pair.left.valid is True
    assert pair.left.sensorName == "left_ultrasonic"
    assert pair.left.distanceCm == 44.16
    assert pair.left.triggerGpio == 7
    assert pair.left.echoGpio == 8

    assert pair.right.valid is True
    assert pair.right.sensorName == "right_ultrasonic"
    assert pair.right.distanceCm == 38.75
    assert pair.right.triggerGpio == 9
    assert pair.right.echoGpio == 10

    print("PASS: valid pair adapted")


def test_adapt_left_invalid_right_valid() -> None:
    print()
    print("========== Arduino Adapter: Left Invalid Right Valid ==========")

    payload = {
        "type": "ultrasonic",
        "seq": 13,
        "ms": 4567,
        "left_cm": None,
        "right_cm": 47.3,
        "left_ok": False,
        "right_ok": True,
        "left_fault": "no_echo",
        "right_fault": "none",
    }

    arduino_reading = parse_arduino_ultrasonic_payload(payload)

    left = arduino_side_to_ultrasonic_reading(
        arduino_reading,
        side="left",
    )

    right = arduino_side_to_ultrasonic_reading(
        arduino_reading,
        side="right",
    )

    pprint(left.to_dict())
    pprint(right.to_dict())

    assert left.valid is False
    assert left.distanceCm is None
    assert left.faultCode == "arduino_left_ultrasonic_no_echo"

    assert right.valid is True
    assert right.distanceCm == 47.3
    assert right.faultCode is None

    print("PASS: invalid left / valid right adapted")


def test_fill_level_from_arduino_left_reading() -> None:
    print()
    print("========== Arduino Adapter: Fill-Level Reuse ==========")

    payload = {
        "type": "ultrasonic",
        "seq": 14,
        "ms": 5678,
        "left_cm": 25.0,
        "right_cm": 45.0,
        "left_ok": True,
        "right_ok": True,
        "left_fault": "none",
        "right_fault": "none",
    }

    arduino_reading = parse_arduino_ultrasonic_payload(payload)
    pair = arduino_reading_to_ultrasonic_pair(arduino_reading)

    fill_config = FillLevelConfig(
        compartment_name="left_compartment",
        empty_distance_cm=45.0,
        full_distance_cm=5.0,
        low_threshold_percent=40.0,
        full_threshold_percent=80.0,
    )

    fill_result = estimate_fill_level_from_ultrasonic(
        reading=pair.left,
        config=fill_config,
    )

    pprint(fill_result.to_dict())

    assert fill_result.valid is True
    assert fill_result.fillPercentage == 50.0
    assert fill_result.capacityLevel == "half"
    assert fill_result.indicatorColor == "yellow"

    print("PASS: fill-level logic reused from Arduino reading")


def test_side_detection_from_arduino_current_readings() -> None:
    print()
    print("========== Arduino Adapter: Side Detection Reuse ==========")

    # Baseline means both compartments were around 45cm before disposal.
    left_baseline = make_baseline_reading(
        sensor_name="left_ultrasonic",
        role="left_compartment_detection_and_fill",
        distance_cm=45.0,
        trigger_gpio=7,
        echo_gpio=8,
    )

    right_baseline = make_baseline_reading(
        sensor_name="right_ultrasonic",
        role="right_compartment_detection_and_fill",
        distance_cm=45.0,
        trigger_gpio=9,
        echo_gpio=10,
    )

    # Current Arduino reading shows right side changed strongly.
    payload = {
        "type": "ultrasonic",
        "seq": 15,
        "ms": 6789,
        "left_cm": 44.0,
        "right_cm": 28.0,
        "left_ok": True,
        "right_ok": True,
        "left_fault": "none",
        "right_fault": "none",
    }

    arduino_reading = parse_arduino_ultrasonic_payload(payload)
    current_pair = arduino_reading_to_ultrasonic_pair(arduino_reading)

    result = detect_side_from_readings(
        left_baseline=left_baseline,
        left_current=current_pair.left,
        right_baseline=right_baseline,
        right_current=current_pair.right,
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )

    pprint(result.to_dict())

    assert result.valid is True
    assert result.detectedSide == "right"
    assert result.disposalSide == "right"

    print("PASS: side detection logic reused from Arduino reading")


def main() -> None:
    test_parse_and_adapt_valid_pair()
    test_adapt_left_invalid_right_valid()
    test_fill_level_from_arduino_left_reading()
    test_side_detection_from_arduino_current_readings()

    print()
    print("All Arduino ultrasonic adapter tests passed.")


if __name__ == "__main__":
    main()

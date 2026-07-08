"""
Test TechBin Arduino capacity monitor.

This test does not touch real Arduino, GPIO, or serial ports.

Run:
    PYTHONPATH=. python3 tests/test_arduino_capacity_monitor.py
"""

from __future__ import annotations

from pprint import pprint

from app.sensors.arduino_bridge import parse_arduino_ultrasonic_payload
from app.sensors.arduino_capacity_monitor import ArduinoCapacityMonitor
from app.sensors.fill_level import FillLevelConfig


def test_low_and_full_capacity() -> None:
    print()
    print("========== Arduino Capacity: Left Low / Right Full ==========")

    payload = {
        "type": "ultrasonic",
        "seq": 101,
        "ms": 12345,
        "left_cm": 40.0,
        "right_cm": 8.0,
        "left_ok": True,
        "right_ok": True,
        "left_fault": "none",
        "right_fault": "none",
    }

    arduino_reading = parse_arduino_ultrasonic_payload(payload)

    monitor = ArduinoCapacityMonitor(
        left_fill_config=FillLevelConfig(
            compartment_name="left_compartment",
            empty_distance_cm=45.0,
            full_distance_cm=5.0,
            low_threshold_percent=40.0,
            full_threshold_percent=80.0,
        ),
        right_fill_config=FillLevelConfig(
            compartment_name="right_compartment",
            empty_distance_cm=45.0,
            full_distance_cm=5.0,
            low_threshold_percent=40.0,
            full_threshold_percent=80.0,
        ),
    )

    result = monitor.evaluate_arduino_reading(arduino_reading)

    pprint(result.to_dict())

    assert result.overallValid is True

    assert result.left["capacityLevel"] == "low"
    assert result.left["indicatorColor"] == "green"

    assert result.right["capacityLevel"] == "full"
    assert result.right["indicatorColor"] == "red"

    print("PASS: left low / right full")


def test_half_capacity_both_sides() -> None:
    print()
    print("========== Arduino Capacity: Both Half ==========")

    payload = {
        "type": "ultrasonic",
        "seq": 102,
        "ms": 22345,
        "left_cm": 25.0,
        "right_cm": 25.0,
        "left_ok": True,
        "right_ok": True,
        "left_fault": "none",
        "right_fault": "none",
    }

    arduino_reading = parse_arduino_ultrasonic_payload(payload)

    monitor = ArduinoCapacityMonitor(
        left_fill_config=FillLevelConfig(
            compartment_name="left_compartment",
            empty_distance_cm=45.0,
            full_distance_cm=5.0,
            low_threshold_percent=40.0,
            full_threshold_percent=80.0,
        ),
        right_fill_config=FillLevelConfig(
            compartment_name="right_compartment",
            empty_distance_cm=45.0,
            full_distance_cm=5.0,
            low_threshold_percent=40.0,
            full_threshold_percent=80.0,
        ),
    )

    result = monitor.evaluate_arduino_reading(arduino_reading)

    pprint(result.to_dict())

    assert result.overallValid is True

    assert result.left["fillPercentage"] == 50.0
    assert result.left["capacityLevel"] == "half"
    assert result.left["indicatorColor"] == "yellow"

    assert result.right["fillPercentage"] == 50.0
    assert result.right["capacityLevel"] == "half"
    assert result.right["indicatorColor"] == "yellow"

    print("PASS: both half")


def test_invalid_left_valid_right() -> None:
    print()
    print("========== Arduino Capacity: Invalid Left / Valid Right ==========")

    payload = {
        "type": "ultrasonic",
        "seq": 103,
        "ms": 32345,
        "left_cm": None,
        "right_cm": 40.0,
        "left_ok": False,
        "right_ok": True,
        "left_fault": "no_echo",
        "right_fault": "none",
    }

    arduino_reading = parse_arduino_ultrasonic_payload(payload)

    monitor = ArduinoCapacityMonitor(
        left_fill_config=FillLevelConfig(
            compartment_name="left_compartment",
            empty_distance_cm=45.0,
            full_distance_cm=5.0,
        ),
        right_fill_config=FillLevelConfig(
            compartment_name="right_compartment",
            empty_distance_cm=45.0,
            full_distance_cm=5.0,
        ),
    )

    result = monitor.evaluate_arduino_reading(arduino_reading)

    pprint(result.to_dict())

    assert result.overallValid is False
    assert result.left["valid"] is False
    assert result.left["capacityLevel"] == "unknown"
    assert result.left["indicatorColor"] == "off"
    assert "left:" in result.faultCodes[0]

    assert result.right["valid"] is True
    assert result.right["capacityLevel"] == "low"
    assert result.right["indicatorColor"] == "green"

    print("PASS: invalid left / valid right")


def main() -> None:
    test_low_and_full_capacity()
    test_half_capacity_both_sides()
    test_invalid_left_valid_right()

    print()
    print("All Arduino capacity monitor tests passed.")


if __name__ == "__main__":
    main()

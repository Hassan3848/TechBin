"""
Test TechBin Arduino side detection monitor.

This test does not touch real Arduino, GPIO, or serial ports.

Run:
    PYTHONPATH=. python3 tests/test_arduino_side_detection_monitor.py
"""

from __future__ import annotations

from pprint import pprint

from app.sensors.arduino_bridge import parse_arduino_ultrasonic_payload
from app.sensors.arduino_side_detection_monitor import ArduinoSideDetectionMonitor
from app.sensors.side_detector import SideDetectionConfig


def make_arduino_reading(
    *,
    seq: int,
    left_cm: float | None,
    right_cm: float | None,
    left_ok: bool = True,
    right_ok: bool = True,
    left_fault: str = "none",
    right_fault: str = "none",
):
    payload = {
        "type": "ultrasonic",
        "seq": seq,
        "ms": seq * 100,
        "left_cm": left_cm,
        "right_cm": right_cm,
        "left_ok": left_ok,
        "right_ok": right_ok,
        "left_fault": left_fault,
        "right_fault": right_fault,
    }

    return parse_arduino_ultrasonic_payload(payload)


def test_baseline_capture_success() -> None:
    print()
    print("========== Arduino Side: Baseline Capture ==========")

    monitor = ArduinoSideDetectionMonitor()

    baseline = make_arduino_reading(
        seq=1,
        left_cm=45.0,
        right_cm=45.0,
    )

    result = monitor.capture_baseline_from_arduino_reading(baseline)

    pprint(result.to_dict())

    assert result.valid is True
    assert result.baselineCaptured is True
    assert result.faultCodes == []

    print("PASS: baseline capture success")


def test_right_side_detected() -> None:
    print()
    print("========== Arduino Side: Right Side Detected ==========")

    monitor = ArduinoSideDetectionMonitor(
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )

    baseline = make_arduino_reading(
        seq=1,
        left_cm=45.0,
        right_cm=45.0,
    )

    current = make_arduino_reading(
        seq=2,
        left_cm=44.0,
        right_cm=28.0,
    )

    baseline_result = monitor.capture_baseline_from_arduino_reading(baseline)
    result = monitor.detect_from_arduino_reading(current)

    pprint(baseline_result.to_dict())
    pprint(result.to_dict())

    assert result.valid is True
    assert result.detectedSide == "right"
    assert result.disposalSide == "right"
    assert result.faultCode is None

    print("PASS: right side detected")


def test_left_side_detected() -> None:
    print()
    print("========== Arduino Side: Left Side Detected ==========")

    monitor = ArduinoSideDetectionMonitor(
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )

    baseline = make_arduino_reading(
        seq=1,
        left_cm=45.0,
        right_cm=45.0,
    )

    current = make_arduino_reading(
        seq=2,
        left_cm=29.0,
        right_cm=44.0,
    )

    monitor.capture_baseline_from_arduino_reading(baseline)
    result = monitor.detect_from_arduino_reading(current)

    pprint(result.to_dict())

    assert result.valid is True
    assert result.detectedSide == "left"
    assert result.disposalSide == "left"
    assert result.faultCode is None

    print("PASS: left side detected")


def test_no_side_detected() -> None:
    print()
    print("========== Arduino Side: No Side Detected ==========")

    monitor = ArduinoSideDetectionMonitor(
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )

    baseline = make_arduino_reading(
        seq=1,
        left_cm=45.0,
        right_cm=45.0,
    )

    current = make_arduino_reading(
        seq=2,
        left_cm=43.0,
        right_cm=42.5,
    )

    monitor.capture_baseline_from_arduino_reading(baseline)
    result = monitor.detect_from_arduino_reading(current)

    pprint(result.to_dict())

    assert result.valid is False
    assert result.detectedSide == "unknown"
    assert result.disposalSide is None
    assert result.faultCode == "no_compartment_disturbance"

    print("PASS: no side detected")


def test_ambiguous_side_detected() -> None:
    print()
    print("========== Arduino Side: Ambiguous Side Detected ==========")

    monitor = ArduinoSideDetectionMonitor(
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )

    baseline = make_arduino_reading(
        seq=1,
        left_cm=45.0,
        right_cm=45.0,
    )

    current = make_arduino_reading(
        seq=2,
        left_cm=30.0,
        right_cm=31.0,
    )

    monitor.capture_baseline_from_arduino_reading(baseline)
    result = monitor.detect_from_arduino_reading(current)

    pprint(result.to_dict())

    assert result.valid is False
    assert result.detectedSide == "ambiguous"
    assert result.disposalSide is None
    assert result.faultCode == "ambiguous_compartment_disturbance"

    print("PASS: ambiguous side detected")


def test_missing_baseline_rejected() -> None:
    print()
    print("========== Arduino Side: Missing Baseline Rejected ==========")

    monitor = ArduinoSideDetectionMonitor()

    current = make_arduino_reading(
        seq=2,
        left_cm=30.0,
        right_cm=45.0,
    )

    result = monitor.detect_from_arduino_reading(current)

    pprint(result.to_dict())

    assert result.valid is False
    assert result.detectedSide == "unknown"
    assert result.faultCode == "arduino_side_baseline_missing"

    print("PASS: missing baseline rejected")


def test_invalid_baseline_rejected() -> None:
    print()
    print("========== Arduino Side: Invalid Baseline Rejected ==========")

    monitor = ArduinoSideDetectionMonitor()

    baseline = make_arduino_reading(
        seq=1,
        left_cm=None,
        right_cm=45.0,
        left_ok=False,
        right_ok=True,
        left_fault="no_echo",
        right_fault="none",
    )

    result = monitor.capture_baseline_from_arduino_reading(baseline)

    pprint(result.to_dict())

    assert result.valid is False
    assert result.baselineCaptured is False
    assert result.faultCodes

    print("PASS: invalid baseline rejected")


def main() -> None:
    test_baseline_capture_success()
    test_right_side_detected()
    test_left_side_detected()
    test_no_side_detected()
    test_ambiguous_side_detected()
    test_missing_baseline_rejected()
    test_invalid_baseline_rejected()

    print()
    print("All Arduino side detection monitor tests passed.")


if __name__ == "__main__":
    main()

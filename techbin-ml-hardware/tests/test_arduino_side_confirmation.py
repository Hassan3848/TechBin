"""
Test TechBin Arduino side confirmation window.

This test does not touch real Arduino, GPIO, or serial ports.

Run:
    PYTHONPATH=. python3 tests/test_arduino_side_confirmation.py
"""

from __future__ import annotations

from pprint import pprint

from app.sensors.arduino_bridge import parse_arduino_ultrasonic_payload
from app.sensors.arduino_side_confirmation import (
    ArduinoSideConfirmationConfig,
    ArduinoSideConfirmationWindow,
    confirm_arduino_side_results,
)
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


def build_monitor() -> ArduinoSideDetectionMonitor:
    monitor = ArduinoSideDetectionMonitor(
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        )
    )

    baseline = make_arduino_reading(
        seq=1,
        left_cm=45.0,
        right_cm=45.0,
    )

    baseline_result = monitor.capture_baseline_from_arduino_reading(baseline)

    assert baseline_result.valid is True

    return monitor


def test_confirm_left_side() -> None:
    print()
    print("========== Arduino Side Confirmation: Confirm Left ==========")

    monitor = build_monitor()

    readings = [
        make_arduino_reading(seq=2, left_cm=30.0, right_cm=44.0),
        make_arduino_reading(seq=3, left_cm=29.0, right_cm=44.0),
        make_arduino_reading(seq=4, left_cm=31.0, right_cm=45.0),
        make_arduino_reading(seq=5, left_cm=30.5, right_cm=44.5),
        make_arduino_reading(seq=6, left_cm=45.0, right_cm=45.0),
    ]

    results = [monitor.detect_from_arduino_reading(reading) for reading in readings]

    confirmation = confirm_arduino_side_results(
        results,
        config=ArduinoSideConfirmationConfig(
            min_samples=5,
            min_valid_side_samples=3,
            winner_ratio=0.65,
            dominance_margin_count=2,
        ),
    )

    pprint(confirmation.to_dict())

    assert confirmation.valid is True
    assert confirmation.confirmed is True
    assert confirmation.confirmedSide == "left"
    assert confirmation.disposalSide == "left"
    assert confirmation.leftCount == 4
    assert confirmation.rightCount == 0

    print("PASS: left side confirmed")


def test_confirm_right_side() -> None:
    print()
    print("========== Arduino Side Confirmation: Confirm Right ==========")

    monitor = build_monitor()

    readings = [
        make_arduino_reading(seq=2, left_cm=44.0, right_cm=30.0),
        make_arduino_reading(seq=3, left_cm=44.0, right_cm=29.0),
        make_arduino_reading(seq=4, left_cm=45.0, right_cm=31.0),
        make_arduino_reading(seq=5, left_cm=44.5, right_cm=30.5),
        make_arduino_reading(seq=6, left_cm=45.0, right_cm=45.0),
    ]

    results = [monitor.detect_from_arduino_reading(reading) for reading in readings]

    confirmation = confirm_arduino_side_results(
        results,
        config=ArduinoSideConfirmationConfig(
            min_samples=5,
            min_valid_side_samples=3,
            winner_ratio=0.65,
            dominance_margin_count=2,
        ),
    )

    pprint(confirmation.to_dict())

    assert confirmation.valid is True
    assert confirmation.confirmed is True
    assert confirmation.confirmedSide == "right"
    assert confirmation.disposalSide == "right"
    assert confirmation.rightCount == 4
    assert confirmation.leftCount == 0

    print("PASS: right side confirmed")


def test_reject_ambiguous_split() -> None:
    print()
    print("========== Arduino Side Confirmation: Reject Ambiguous Split ==========")

    monitor = build_monitor()

    readings = [
        make_arduino_reading(seq=2, left_cm=30.0, right_cm=44.0),
        make_arduino_reading(seq=3, left_cm=29.0, right_cm=44.0),
        make_arduino_reading(seq=4, left_cm=44.0, right_cm=30.0),
        make_arduino_reading(seq=5, left_cm=44.0, right_cm=29.0),
        make_arduino_reading(seq=6, left_cm=45.0, right_cm=45.0),
        make_arduino_reading(seq=7, left_cm=45.0, right_cm=45.0),
    ]

    results = [monitor.detect_from_arduino_reading(reading) for reading in readings]

    confirmation = confirm_arduino_side_results(
        results,
        config=ArduinoSideConfirmationConfig(
            min_samples=5,
            min_valid_side_samples=3,
            winner_ratio=0.65,
            dominance_margin_count=2,
        ),
    )

    pprint(confirmation.to_dict())

    assert confirmation.valid is False
    assert confirmation.confirmed is False
    assert confirmation.confirmedSide == "ambiguous"
    assert confirmation.disposalSide is None
    assert confirmation.faultCode in {
        "no_dominant_side",
        "winner_ratio_too_low",
        "dominance_margin_too_low",
    }

    print("PASS: ambiguous split rejected")


def test_reject_no_movement() -> None:
    print()
    print("========== Arduino Side Confirmation: Reject No Movement ==========")

    monitor = build_monitor()

    readings = [
        make_arduino_reading(seq=2, left_cm=45.0, right_cm=45.0),
        make_arduino_reading(seq=3, left_cm=44.5, right_cm=45.2),
        make_arduino_reading(seq=4, left_cm=45.3, right_cm=44.9),
        make_arduino_reading(seq=5, left_cm=45.1, right_cm=45.0),
        make_arduino_reading(seq=6, left_cm=45.0, right_cm=45.0),
    ]

    results = [monitor.detect_from_arduino_reading(reading) for reading in readings]

    window = ArduinoSideConfirmationWindow(
        config=ArduinoSideConfirmationConfig(
            min_samples=5,
            min_valid_side_samples=3,
            winner_ratio=0.65,
            dominance_margin_count=2,
        ),
    )

    window.add_samples(results)
    confirmation = window.decide()

    pprint(confirmation.to_dict())

    assert confirmation.valid is False
    assert confirmation.confirmed is False
    assert confirmation.confirmedSide == "unknown"
    assert confirmation.faultCode == "insufficient_valid_side_samples"

    print("PASS: no movement rejected")


def test_reject_insufficient_samples() -> None:
    print()
    print("========== Arduino Side Confirmation: Reject Insufficient Samples ==========")

    monitor = build_monitor()

    readings = [
        make_arduino_reading(seq=2, left_cm=30.0, right_cm=44.0),
        make_arduino_reading(seq=3, left_cm=29.0, right_cm=44.0),
    ]

    results = [monitor.detect_from_arduino_reading(reading) for reading in readings]

    confirmation = confirm_arduino_side_results(
        results,
        config=ArduinoSideConfirmationConfig(
            min_samples=5,
            min_valid_side_samples=3,
            winner_ratio=0.65,
            dominance_margin_count=2,
        ),
    )

    pprint(confirmation.to_dict())

    assert confirmation.valid is False
    assert confirmation.confirmed is False
    assert confirmation.faultCode == "insufficient_samples"

    print("PASS: insufficient samples rejected")


def main() -> None:
    test_confirm_left_side()
    test_confirm_right_side()
    test_reject_ambiguous_split()
    test_reject_no_movement()
    test_reject_insufficient_samples()

    print()
    print("All Arduino side confirmation tests passed.")


if __name__ == "__main__":
    main()

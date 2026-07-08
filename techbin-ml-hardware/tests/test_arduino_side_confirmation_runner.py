"""
Test TechBin fast Arduino side confirmation runner.

This test does not touch real Arduino, GPIO, or serial ports.

Run:
    PYTHONPATH=. python3 tests/test_arduino_side_confirmation_runner.py
"""

from __future__ import annotations

from pprint import pprint

from app.sensors.arduino_bridge import parse_arduino_ultrasonic_payload
from app.sensors.arduino_side_confirmation_runner import (
    FastArduinoSideConfirmationConfig,
    FastArduinoSideConfirmationRunner,
)


class FakeArduinoBridge:
    def __init__(self, readings):
        self.readings = list(readings)

    def read_ultrasonic_once(self):
        if not self.readings:
            raise RuntimeError("Fake bridge has no more readings.")

        return self.readings.pop(0)


def make_reading(seq: int, left_cm: float, right_cm: float):
    return parse_arduino_ultrasonic_payload(
        {
            "type": "ultrasonic",
            "seq": seq,
            "ms": seq * 100,
            "left_cm": left_cm,
            "right_cm": right_cm,
            "left_ok": True,
            "right_ok": True,
            "left_fault": "none",
            "right_fault": "none",
        }
    )


def test_fast_confirm_left_early() -> None:
    print()
    print("========== Fast Runner: Confirm Left Early ==========")

    readings = [
        make_reading(1, 45.0, 45.0),  # baseline
        make_reading(2, 30.0, 44.0),
        make_reading(3, 29.0, 44.0),
        make_reading(4, 28.0, 44.0),
        make_reading(5, 27.0, 44.0),
    ]

    bridge = FakeArduinoBridge(readings)

    runner = FastArduinoSideConfirmationRunner(
        config=FastArduinoSideConfirmationConfig(
            max_confirm_seconds=2.0,
            max_samples_per_window=6,
            early_min_samples=3,
            early_win_count=3,
            early_winner_ratio=0.80,
            early_dominance_margin_count=2,
            final_min_samples=3,
            final_min_valid_side_samples=2,
            final_winner_ratio=0.65,
            final_dominance_margin_count=1,
        )
    )

    baseline = runner.capture_baseline(bridge)
    result = runner.confirm_once(bridge)

    pprint(baseline.to_dict())
    pprint(result.to_dict())

    assert baseline.valid is True
    assert result.valid is True
    assert result.confirmed is True
    assert result.confirmedSide == "left"
    assert result.disposalSide == "left"
    assert result.reason == "early_confirmed"
    assert result.samplesCollected == 3

    print("PASS: fast left confirmed early")


def test_fast_confirm_right_early() -> None:
    print()
    print("========== Fast Runner: Confirm Right Early ==========")

    readings = [
        make_reading(1, 45.0, 45.0),  # baseline
        make_reading(2, 44.0, 30.0),
        make_reading(3, 44.0, 29.0),
        make_reading(4, 44.0, 28.0),
        make_reading(5, 44.0, 27.0),
    ]

    bridge = FakeArduinoBridge(readings)

    runner = FastArduinoSideConfirmationRunner(
        config=FastArduinoSideConfirmationConfig(
            max_confirm_seconds=2.0,
            max_samples_per_window=6,
            early_min_samples=3,
            early_win_count=3,
            early_winner_ratio=0.80,
            early_dominance_margin_count=2,
            final_min_samples=3,
            final_min_valid_side_samples=2,
            final_winner_ratio=0.65,
            final_dominance_margin_count=1,
        )
    )

    baseline = runner.capture_baseline(bridge)
    result = runner.confirm_once(bridge)

    pprint(baseline.to_dict())
    pprint(result.to_dict())

    assert baseline.valid is True
    assert result.valid is True
    assert result.confirmed is True
    assert result.confirmedSide == "right"
    assert result.disposalSide == "right"
    assert result.reason == "early_confirmed"
    assert result.samplesCollected == 3

    print("PASS: fast right confirmed early")


def test_fast_reject_no_movement() -> None:
    print()
    print("========== Fast Runner: Reject No Movement ==========")

    readings = [
        make_reading(1, 45.0, 45.0),  # baseline
        make_reading(2, 45.0, 45.0),
        make_reading(3, 44.8, 45.1),
        make_reading(4, 45.2, 44.9),
        make_reading(5, 45.0, 45.0),
    ]

    bridge = FakeArduinoBridge(readings)

    runner = FastArduinoSideConfirmationRunner(
        config=FastArduinoSideConfirmationConfig(
            max_confirm_seconds=2.0,
            max_samples_per_window=4,
            early_min_samples=3,
            early_win_count=3,
            early_winner_ratio=0.80,
            early_dominance_margin_count=2,
            final_min_samples=3,
            final_min_valid_side_samples=2,
            final_winner_ratio=0.65,
            final_dominance_margin_count=1,
        )
    )

    baseline = runner.capture_baseline(bridge)
    result = runner.confirm_once(bridge)

    pprint(baseline.to_dict())
    pprint(result.to_dict())

    assert baseline.valid is True
    assert result.valid is False
    assert result.confirmed is False
    assert result.confirmedSide == "unknown"
    assert result.disposalSide is None

    print("PASS: no movement rejected")


def main() -> None:
    test_fast_confirm_left_early()
    test_fast_confirm_right_early()
    test_fast_reject_no_movement()

    print()
    print("All fast Arduino side confirmation runner tests passed.")


if __name__ == "__main__":
    main()

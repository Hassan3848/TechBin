#!/usr/bin/env python3
"""
Raw BCM GPIO21 metal detector signal test.

This script does not import or run the TechBin app.

Expected raw levels with internal pull-up enabled:
    HIGH -> NO METAL
    LOW  -> METAL DETECTED
"""

from __future__ import annotations

import time


GPIO_PIN = 21


def main() -> None:
    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        raise SystemExit(
            "RPi.GPIO is required. Install with: sudo apt install -y python3-rpi.gpio"
        ) from exc

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    try:
        print("Raw BCM GPIO21 test with internal pull-up. Press Ctrl+C to stop.")
        while True:
            level = GPIO.input(GPIO_PIN)
            if level == GPIO.HIGH:
                print("HIGH = NO METAL")
            else:
                print("LOW = METAL DETECTED")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print()
    finally:
        GPIO.cleanup(GPIO_PIN)


if __name__ == "__main__":
    main()

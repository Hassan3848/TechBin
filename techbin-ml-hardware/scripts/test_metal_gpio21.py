#!/usr/bin/env python3
"""
Standalone GPIO21 metal detector check for the isolated PC817 output.

Expected signal:
    HIGH -> NO METAL
    LOW  -> METAL DETECTED

Wiring:
    PC817 V1            -> BCM GPIO21 / physical pin 40
    PC817 output-side G -> Raspberry Pi GND / physical pin 39

This script enables gpiozero's internal pull-up for this direct GPIO check.
"""

from __future__ import annotations

import time


GPIO = 21


def main() -> None:
    try:
        from gpiozero import DigitalInputDevice
    except ImportError as exc:
        raise SystemExit(
            "gpiozero is required. Install with: sudo apt install -y python3-gpiozero"
        ) from exc

    device = DigitalInputDevice(pin=GPIO, pull_up=True)
    try:
        print("Reading BCM GPIO21. Press Ctrl+C to stop.")
        while True:
            if device.value:
                print("NO METAL")
            else:
                print("METAL DETECTED")
            time.sleep(0.25)
    except KeyboardInterrupt:
        print()
    finally:
        device.close()


if __name__ == "__main__":
    main()

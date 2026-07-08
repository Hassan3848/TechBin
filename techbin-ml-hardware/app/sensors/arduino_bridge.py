"""
TechBin Arduino serial bridge.

Purpose:
    Read filtered left/right ultrasonic sensor data from Arduino Uno over USB Serial.

Architecture:
    Raspberry Pi:
        camera, ML inference, event processing, telemetry, logs

    Arduino Uno:
        left/right HC-SR04 timing and filtering
        sends JSON lines over USB Serial

Expected Arduino JSON:
    {"type":"ultrasonic","seq":12,"ms":3456,"left_cm":32.41,"right_cm":45.22,"left_ok":true,"right_ok":true,"left_fault":"none","right_fault":"none"}
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.logger import get_logger


logger = get_logger(__name__)


class ArduinoBridgeError(RuntimeError):
    """Raised when Arduino serial bridge fails."""


@dataclass(frozen=True)
class ArduinoUltrasonicReading:
    """
    Parsed left/right ultrasonic reading from Arduino.
    """

    timestamp: str
    sequence: int | None
    arduinoMillis: int | None
    leftCm: float | None
    rightCm: float | None
    leftOk: bool
    rightOk: bool
    leftFault: str | None
    rightFault: str | None
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


class ArduinoSerialBridge:
    """
    Serial reader for Arduino Uno sensor controller.
    """

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baudrate: int = 115200,
        timeout_seconds: float = 2.0,
        startup_wait_seconds: float = 2.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout_seconds = timeout_seconds
        self.startup_wait_seconds = startup_wait_seconds
        self._serial = None

    def open(self) -> None:
        try:
            import serial
        except ImportError as exc:
            raise ArduinoBridgeError(
                "pyserial is not installed. Install with: sudo apt install -y python3-serial"
            ) from exc

        try:
            self._serial = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout_seconds,
            )

            time.sleep(self.startup_wait_seconds)

            logger.info(
                "Arduino serial bridge opened | port=%s | baudrate=%s",
                self.port,
                self.baudrate,
            )

        except Exception as exc:
            raise ArduinoBridgeError(
                f"Failed to open Arduino serial port {self.port}: {exc}"
            ) from exc

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def __enter__(self) -> "ArduinoSerialBridge":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def read_json_line(self) -> dict[str, Any]:
        if self._serial is None:
            raise ArduinoBridgeError("Serial bridge is not open.")

        line_bytes = self._serial.readline()

        if not line_bytes:
            raise ArduinoBridgeError("Timed out waiting for Arduino serial line.")

        try:
            line = line_bytes.decode("utf-8", errors="replace").strip()
        except Exception as exc:
            raise ArduinoBridgeError(f"Failed to decode serial bytes: {exc}") from exc

        if not line:
            raise ArduinoBridgeError("Received empty serial line from Arduino.")

        # Serial streams can occasionally contain junk before/after a JSON object,
        # especially right after Arduino reset, USB noise, or very fast output.
        # Examples:
        #   _{"type":"ultrasonic",...}
        #   {"type":"ultrasonic",...}garbage
        # Production behavior: keep the first complete-looking JSON object.
        if "{" in line and not line.startswith("{"):
            logger.warning("Trimming leading serial noise before JSON: %r", line)
            line = line[line.find("{"):]

        if "}" in line and not line.endswith("}"):
            logger.warning("Trimming trailing serial noise after JSON: %r", line)
            line = line[: line.rfind("}") + 1]

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ArduinoBridgeError(
                f"Arduino line is not valid JSON: {line}"
            ) from exc

        return payload

    def read_ultrasonic_once(
        self,
        max_lines: int = 25,
    ) -> ArduinoUltrasonicReading:
        """
        Read until an ultrasonic message is found.

        Boot/status lines are skipped.

        Production behavior:
            A single corrupted serial line must not crash the runtime.
            Serial streams can occasionally contain partial/merged lines,
            especially after resets, USB noise, or fast Arduino output.

            This method skips malformed lines and keeps reading until a valid
            ultrasonic JSON message is found or max_lines is exceeded.
        """

        last_error: Exception | None = None

        for _ in range(max_lines):
            try:
                payload = self.read_json_line()
            except ArduinoBridgeError as exc:
                last_error = exc
                logger.warning("Skipping malformed Arduino serial line: %s", exc)
                continue

            message_type = payload.get("type")

            if message_type != "ultrasonic":
                logger.info("Skipping Arduino message type=%s", message_type)
                continue

            return parse_arduino_ultrasonic_payload(payload)

        raise ArduinoBridgeError(
            f"No valid ultrasonic message received within {max_lines} serial lines. "
            f"Last error: {last_error}"
        )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_arduino_ultrasonic_payload(
    payload: dict[str, Any],
) -> ArduinoUltrasonicReading:
    """
    Validate and normalize Arduino ultrasonic JSON payload.
    """

    if payload.get("type") != "ultrasonic":
        raise ArduinoBridgeError(
            f"Expected type='ultrasonic', got {payload.get('type')!r}"
        )

    left_ok = bool(payload.get("left_ok", False))
    right_ok = bool(payload.get("right_ok", False))

    return ArduinoUltrasonicReading(
        timestamp=_now_iso(),
        sequence=_int_or_none(payload.get("seq")),
        arduinoMillis=_int_or_none(payload.get("ms")),
        leftCm=_float_or_none(payload.get("left_cm")),
        rightCm=_float_or_none(payload.get("right_cm")),
        leftOk=left_ok,
        rightOk=right_ok,
        leftFault=payload.get("left_fault"),
        rightFault=payload.get("right_fault"),
        raw=payload,
    )


def find_likely_arduino_ports() -> list[str]:
    """
    Return likely Arduino serial ports on Linux.
    """

    candidates = []

    for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
        candidates.extend(str(path) for path in Path("/").glob(pattern.lstrip("/")))

    return sorted(candidates)


__all__ = [
    "ArduinoBridgeError",
    "ArduinoUltrasonicReading",
    "ArduinoSerialBridge",
    "parse_arduino_ultrasonic_payload",
    "find_likely_arduino_ports",
]

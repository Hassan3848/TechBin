"""
Focused tests for Pi health supervisor and optional module gates.

Run from project root:
    PYTHONPATH=. python3 tests/test_health_supervisor_optional_modules.py
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import app.telemetry.supabase as supabase_module
from app.sensors.health_supervisor import (
    CRITICAL,
    DISABLED,
    HEALTHY,
    HealthThresholds,
    HardwareHealthSupervisor,
    generic_faults_from_health,
)
from app.sensors.metal_override import evaluate_metal_override
from app.telemetry.supabase import build_bin_state_payload
from app.voice_feedback import DisabledVoiceFeedbackBackend, VoiceFeedback


class DictObservation:
    def __init__(self, data: dict) -> None:
        self.data = data

    def to_dict(self) -> dict:
        return self.data


class RecordingVoiceBackend(DisabledVoiceFeedbackBackend):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def play(self, message_key: str, text: str) -> None:
        self.calls.append((message_key, text))


def valid_reading(sensor: str = "left_ultrasonic", distance: float = 100.0) -> dict:
    return {
        "sensorName": sensor,
        "valid": True,
        "distanceCm": distance,
        "faultCode": None,
        "message": "valid far distance",
    }


def invalid_reading(sensor: str = "left_ultrasonic", fault: str = "echo_timeout") -> dict:
    return {
        "sensorName": sensor,
        "valid": False,
        "distanceCm": None,
        "faultCode": fault,
        "message": "No valid echo after configured retries.",
    }


def test_transient_ultrasonic_failure_is_not_critical() -> None:
    supervisor = HardwareHealthSupervisor(
        thresholds=HealthThresholds(warning_failures=2, critical_failures=3, recovery_successes=2)
    )
    record = supervisor.observe_ultrasonic("left_ultrasonic", invalid_reading())

    assert record.status != CRITICAL
    assert record.consecutiveFailures == 1


def test_repeated_failure_targets_correct_sensor() -> None:
    supervisor = HardwareHealthSupervisor(
        thresholds=HealthThresholds(warning_failures=2, critical_failures=3, recovery_successes=2)
    )
    for _ in range(3):
        left = supervisor.observe_ultrasonic("left_ultrasonic", invalid_reading("left_ultrasonic"))

    right = supervisor.snapshot()["components"]["right_ultrasonic"]
    assert left.status == CRITICAL
    assert left.faultCode == "echo_timeout"
    assert right["status"] != CRITICAL


def test_valid_readings_recover_after_failure() -> None:
    supervisor = HardwareHealthSupervisor(
        thresholds=HealthThresholds(warning_failures=1, critical_failures=2, recovery_successes=2)
    )
    supervisor.observe_ultrasonic("right_ultrasonic", invalid_reading("right_ultrasonic"))
    supervisor.observe_ultrasonic("right_ultrasonic", invalid_reading("right_ultrasonic"))
    supervisor.observe_ultrasonic("right_ultrasonic", valid_reading("right_ultrasonic"))
    recovered = supervisor.observe_ultrasonic("right_ultrasonic", valid_reading("right_ultrasonic"))

    assert recovered.status == HEALTHY
    assert recovered.faultCode is None


def test_no_disturbance_is_not_health_fault() -> None:
    supervisor = HardwareHealthSupervisor()
    record = supervisor.observe_ultrasonic(
        "left_ultrasonic",
        {"valid": False, "faultCode": "no_compartment_disturbance", "message": "No clear compartment disturbance."},
    )

    assert record.status == HEALTHY
    assert record.faultCode is None


def test_valid_metal_detector_reading_is_healthy() -> None:
    supervisor = HardwareHealthSupervisor(
        metal_enabled=True,
        thresholds=HealthThresholds(warning_failures=2, critical_failures=3, recovery_successes=2),
    )
    record = supervisor.observe_metal_detector(
        {
            "valid": True,
            "metalDetected": True,
            "faultCode": None,
        }
    )

    assert record.status == HEALTHY
    assert record.faultCode is None


def test_invalid_metal_detector_reading_is_warning() -> None:
    supervisor = HardwareHealthSupervisor(
        metal_enabled=True,
        thresholds=HealthThresholds(warning_failures=2, critical_failures=3, recovery_successes=2),
    )
    record = supervisor.observe_metal_detector(
        {
            "valid": False,
            "metalDetected": None,
            "faultCode": "metal_sensor_no_valid_samples",
            "message": "No valid metal sensor samples.",
        }
    )

    assert record.status == "warning"
    assert record.faultCode == "metal_sensor_no_valid_samples"


def test_camera_exception_maps_to_critical_without_raising() -> None:
    supervisor = HardwareHealthSupervisor()
    record = supervisor.observe_camera_exception(RuntimeError("camera failed"))

    assert record.status == CRITICAL
    assert record.faultCode == "camera_exception"


def test_disabled_metal_and_voice_are_not_faults() -> None:
    supervisor = HardwareHealthSupervisor(metal_enabled=False, voice_enabled=False)
    snapshot = supervisor.snapshot()

    assert snapshot["components"]["metal_detector"]["status"] == DISABLED
    assert snapshot["components"]["voice_feedback"]["status"] == DISABLED
    faults = generic_faults_from_health(snapshot)
    assert faults["metal"] is False


def test_metal_override_inactive_while_disabled() -> None:
    result = evaluate_metal_override(
        {"valid": True, "metalDetected": True},
        hardware_healthy=True,
        enabled=False,
    )

    assert result.active is False
    assert result.reason == "metal_override_disabled"


def test_disabled_voice_noop_and_no_payload_history() -> None:
    voice = VoiceFeedback(backend=DisabledVoiceFeedbackBackend())
    event = {
        "placementConfirmed": True,
        "correct": True,
        "expectedSide": "recyclable",
    }

    assert voice.play_after_confirmation(event) is True
    payload = build_bin_state_payload(
        statistics={},
        sensors={},
        faults={},
        latest_event={
            "eventId": "test-event",
            "placementConfirmed": True,
        },
    )
    assert "voice" not in payload
    assert "voiceFeedback" not in payload


def test_voice_only_after_valid_confirmation() -> None:
    backend = RecordingVoiceBackend()
    voice = VoiceFeedback(backend=backend)

    assert voice.play_after_confirmation(None) is False
    assert voice.play_after_confirmation({"placementConfirmed": False, "correct": True, "expectedSide": "recyclable"}) is False
    assert voice.play_after_confirmation({"placementConfirmed": True, "correct": True, "expectedSide": "recyclable"}) is True
    assert len(backend.calls) == 1
    assert backend.calls[0][0] == "correct"


def test_detailed_health_payload_key_is_gated() -> None:
    original_settings = supabase_module.settings
    supabase_module.settings = replace(
        original_settings,
        health=replace(
            original_settings.health,
            detailed_telemetry_enabled=False,
        ),
    )
    try:
        payload = build_bin_state_payload(
            statistics={},
            sensors={},
            faults={},
            detailed_health={"frontUltrasonic": {"status": "healthy"}},
        )
    finally:
        supabase_module.settings = original_settings

    assert "hardwareHealth" not in payload


def test_queue_backlog_statuses() -> None:
    with TemporaryDirectory(prefix="techbin_health_queue_") as tmpdir:
        root = Path(tmpdir)
        pending = root / "pending"
        pending.mkdir(parents=True)
        for index in range(2):
            (pending / f"{index}.json").write_text("{}", encoding="utf-8")

        supervisor = HardwareHealthSupervisor(
            thresholds=HealthThresholds(queue_warning_pending=2, queue_critical_pending=5)
        )
        record = supervisor.observe_telemetry_queue(root)

    assert record.status == "warning"
    assert record.faultCode == "telemetry_queue_backlog_warning"


def test_payload_has_last_checked_at_for_unobserved_telemetry_queue() -> None:
    supervisor = HardwareHealthSupervisor(metal_enabled=False, voice_enabled=False)
    payload = supervisor.to_payload()

    datetime.fromisoformat(payload["telemetryQueue"]["lastCheckedAt"])


def main() -> None:
    test_transient_ultrasonic_failure_is_not_critical()
    test_repeated_failure_targets_correct_sensor()
    test_valid_readings_recover_after_failure()
    test_no_disturbance_is_not_health_fault()
    test_valid_metal_detector_reading_is_healthy()
    test_invalid_metal_detector_reading_is_warning()
    test_camera_exception_maps_to_critical_without_raising()
    test_disabled_metal_and_voice_are_not_faults()
    test_metal_override_inactive_while_disabled()
    test_disabled_voice_noop_and_no_payload_history()
    test_voice_only_after_valid_confirmation()
    test_detailed_health_payload_key_is_gated()
    test_queue_backlog_statuses()
    test_payload_has_last_checked_at_for_unobserved_telemetry_queue()
    print("All health supervisor optional module tests passed.")


if __name__ == "__main__":
    main()

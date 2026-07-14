"""
Stateful per-component health supervisor for TechBin Pi hardware.

The supervisor consumes observations from the runtime pipeline. It does not
open GPIO sensors or a camera on its own, so live disposal reads remain the
single source of hardware access.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app.config import settings


HEALTHY = "healthy"
WARNING = "warning"
CRITICAL = "critical"
DISABLED = "disabled"
NOT_INSTALLED = "not_installed"
UNKNOWN = "unknown"

VALID_STATUSES = (HEALTHY, WARNING, CRITICAL, DISABLED, NOT_INSTALLED, UNKNOWN)

NORMAL_NON_FAULT_CODES = {
    "no_compartment_disturbance",
    "ambiguous_compartment_disturbance",
}


@dataclass(frozen=True)
class HealthThresholds:
    warning_failures: int = 2
    critical_failures: int = 3
    recovery_successes: int = 2
    queue_warning_pending: int = 10
    queue_critical_pending: int = 100

    @classmethod
    def from_settings(cls) -> "HealthThresholds":
        return cls(
            warning_failures=max(1, settings.health.ultrasonic_warning_failures),
            critical_failures=max(1, settings.health.ultrasonic_critical_failures),
            recovery_successes=max(1, settings.health.ultrasonic_recovery_successes),
            queue_warning_pending=max(1, settings.health.queue_warning_pending),
            queue_critical_pending=max(1, settings.health.queue_critical_pending),
        )


@dataclass
class ComponentHealth:
    componentId: str
    displayName: str
    status: str = UNKNOWN
    faultCode: str | None = None
    message: str = "No health observation has been recorded."
    consecutiveFailures: int = 0
    consecutiveSuccesses: int = 0
    lastCheckedAt: str | None = None
    lastSuccessAt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _is_valid_iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or value.strip() == "":
        return False

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False

    return True


def _camel_component_id(component_id: str) -> str:
    parts = component_id.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _copy_record(record: ComponentHealth) -> ComponentHealth:
    return ComponentHealth(**record.to_dict())


class HardwareHealthSupervisor:
    """
    Maintains safe health status for current and optional Pi modules.
    """

    COMPONENT_NAMES = {
        "front_ultrasonic": "Front ultrasonic",
        "left_ultrasonic": "Left ultrasonic",
        "right_ultrasonic": "Right ultrasonic",
        "camera": "Camera",
        "network": "Network",
        "metal_detector": "Metal detector",
        "voice_feedback": "Voice feedback",
        "telemetry_queue": "Telemetry queue",
    }

    def __init__(
        self,
        *,
        thresholds: HealthThresholds | None = None,
        metal_enabled: bool | None = None,
        voice_enabled: bool | None = None,
    ) -> None:
        self.thresholds = thresholds or HealthThresholds.from_settings()
        self._components = {
            component_id: ComponentHealth(
                componentId=component_id,
                displayName=display_name,
            )
            for component_id, display_name in self.COMPONENT_NAMES.items()
        }

        self.set_static_status(
            "metal_detector",
            status=UNKNOWN if (settings.device.metal_override_enabled if metal_enabled is None else metal_enabled) else DISABLED,
            fault_code=None,
            message=(
                "Metal detector override is enabled but no health observation has been recorded."
                if (settings.device.metal_override_enabled if metal_enabled is None else metal_enabled)
                else "Metal detector override is intentionally disabled."
            ),
        )
        self.set_static_status(
            "voice_feedback",
            status=UNKNOWN if (settings.voice_feedback.enabled if voice_enabled is None else voice_enabled) else DISABLED,
            fault_code=None,
            message=(
                "Voice feedback is enabled but no backend health observation has been recorded."
                if (settings.voice_feedback.enabled if voice_enabled is None else voice_enabled)
                else "Voice feedback is intentionally disabled."
            ),
        )
        self.set_static_status(
            "network",
            status=UNKNOWN,
            fault_code=None,
            message="No network upload attempt has been recorded.",
        )

    def set_static_status(
        self,
        component_id: str,
        *,
        status: str,
        fault_code: str | None,
        message: str,
    ) -> ComponentHealth:
        if status not in VALID_STATUSES:
            raise ValueError(f"Unsupported health status: {status}")

        record = self._components[component_id]
        now = _now_iso()
        record.status = status
        record.faultCode = fault_code
        record.message = message
        record.lastCheckedAt = now
        if status == HEALTHY:
            record.lastSuccessAt = now
            record.consecutiveSuccesses += 1
            record.consecutiveFailures = 0
        return _copy_record(record)

    def observe_ultrasonic(
        self,
        component_id: str,
        observation: Any,
        *,
        normal_fault_codes: Iterable[str | None] = NORMAL_NON_FAULT_CODES,
    ) -> ComponentHealth:
        data = observation.to_dict() if hasattr(observation, "to_dict") else observation
        if not isinstance(data, dict):
            data = {"valid": False, "faultCode": "invalid_health_observation", "message": str(observation)}

        valid = bool(data.get("valid"))
        fault_code = data.get("faultCode")
        message = str(data.get("message") or "")

        if valid or fault_code in set(normal_fault_codes):
            return self._record_success(
                component_id,
                message=message or "Valid ultrasonic observation received.",
            )

        return self._record_failure(
            component_id,
            fault_code=str(fault_code or "ultrasonic_invalid"),
            message=message or "Invalid ultrasonic observation received.",
        )

    def observe_camera_success(self, message: str = "Camera capture/inference succeeded.") -> ComponentHealth:
        return self._record_success("camera", message=message)

    def observe_camera_exception(self, exc: Exception | str, *, critical: bool = True) -> ComponentHealth:
        return self._record_failure(
            "camera",
            fault_code="camera_exception",
            message=str(exc),
            force_status=CRITICAL if critical else WARNING,
        )

    def observe_network_result(self, *, ok: bool, message: str, fault_code: str | None = None) -> ComponentHealth:
        if ok:
            return self._record_success("network", message=message)
        return self._record_failure(
            "network",
            fault_code=fault_code or "network_request_failed",
            message=message,
            force_status=WARNING,
        )

    def observe_metal_detector(self, observation: Any) -> ComponentHealth:
        data = observation.to_dict() if hasattr(observation, "to_dict") else observation
        if not isinstance(data, dict):
            data = {
                "valid": False,
                "faultCode": "invalid_health_observation",
                "message": str(observation),
            }

        if bool(data.get("valid")):
            detected = data.get("metalDetected")
            return self._record_success(
                "metal_detector",
                message=f"Valid metal detector observation received; metalDetected={detected}.",
            )

        return self._record_failure(
            "metal_detector",
            fault_code=str(data.get("faultCode") or "metal_detector_invalid"),
            message=str(data.get("message") or "Invalid metal detector observation received."),
            force_status=WARNING,
        )

    def observe_telemetry_queue(self, queue_root: str | Path) -> ComponentHealth:
        root = Path(queue_root)
        pending = root / "pending"
        failed = root / "failed"
        pending_count = len(list(pending.glob("*.json"))) if pending.exists() else 0
        failed_count = len(list(failed.glob("*.json"))) if failed.exists() else 0

        if failed_count > 0:
            return self._set_component(
                "telemetry_queue",
                status=WARNING,
                fault_code="telemetry_failed_items_present",
                message=f"Telemetry queue has {failed_count} failed item(s).",
                success=False,
            )

        if pending_count >= self.thresholds.queue_critical_pending:
            return self._set_component(
                "telemetry_queue",
                status=CRITICAL,
                fault_code="telemetry_queue_backlog_critical",
                message=f"Telemetry queue has {pending_count} pending item(s).",
                success=False,
            )

        if pending_count >= self.thresholds.queue_warning_pending:
            return self._set_component(
                "telemetry_queue",
                status=WARNING,
                fault_code="telemetry_queue_backlog_warning",
                message=f"Telemetry queue has {pending_count} pending item(s).",
                success=False,
            )

        return self._record_success(
            "telemetry_queue",
            message=f"Telemetry queue backlog is acceptable ({pending_count} pending).",
        )

    def _record_success(self, component_id: str, *, message: str) -> ComponentHealth:
        record = self._components[component_id]
        recovered = record.status in (WARNING, CRITICAL)
        record.consecutiveSuccesses += 1
        record.consecutiveFailures = 0

        if record.consecutiveSuccesses >= self.thresholds.recovery_successes or record.status in (UNKNOWN, DISABLED, NOT_INSTALLED):
            status = HEALTHY
            fault_code = None
            if recovered:
                message = "Recovered after valid readings resumed."
        else:
            status = record.status
            fault_code = record.faultCode

        return self._set_component(
            component_id,
            status=status,
            fault_code=fault_code,
            message=message,
            success=True,
            preserve_counts=True,
        )

    def _record_failure(
        self,
        component_id: str,
        *,
        fault_code: str,
        message: str,
        force_status: str | None = None,
    ) -> ComponentHealth:
        record = self._components[component_id]
        record.consecutiveFailures += 1
        record.consecutiveSuccesses = 0

        if force_status is not None:
            status = force_status
        elif record.consecutiveFailures >= self.thresholds.critical_failures:
            status = CRITICAL
        elif record.consecutiveFailures >= self.thresholds.warning_failures:
            status = WARNING
        else:
            status = record.status if record.status != UNKNOWN else HEALTHY

        return self._set_component(
            component_id,
            status=status,
            fault_code=fault_code,
            message=message,
            success=False,
            preserve_counts=True,
        )

    def _set_component(
        self,
        component_id: str,
        *,
        status: str,
        fault_code: str | None,
        message: str,
        success: bool,
        preserve_counts: bool = False,
    ) -> ComponentHealth:
        record = self._components[component_id]
        now = _now_iso()
        record.status = status
        record.faultCode = fault_code
        record.message = message
        record.lastCheckedAt = now

        if not preserve_counts:
            if success:
                record.consecutiveSuccesses += 1
                record.consecutiveFailures = 0
            else:
                record.consecutiveFailures += 1
                record.consecutiveSuccesses = 0

        if success:
            record.lastSuccessAt = now

        return _copy_record(record)

    def snapshot(self) -> dict[str, Any]:
        generated_at = _now_iso()
        components = {
            component_id: _copy_record(record).to_dict()
            for component_id, record in self._components.items()
        }
        for record in components.values():
            if not _is_valid_iso_timestamp(record.get("lastCheckedAt")):
                record["lastCheckedAt"] = generated_at

        overall_status = HEALTHY
        statuses = [record["status"] for record in components.values()]
        if CRITICAL in statuses:
            overall_status = CRITICAL
        elif WARNING in statuses or UNKNOWN in statuses:
            overall_status = WARNING

        return {
            "schemaVersion": 1,
            "generatedAt": generated_at,
            "overallStatus": overall_status,
            "components": components,
        }

    def to_payload(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            _camel_component_id(component_id): record
            for component_id, record in snapshot["components"].items()
        }


def generic_faults_from_health(snapshot: dict[str, Any]) -> dict[str, bool]:
    components = snapshot.get("components", {})

    def is_fault(*ids: str) -> bool:
        return any(
            ((components.get(component_id) or {}).get("status") == CRITICAL)
            for component_id in ids
        )

    return {
        "camera": is_fault("camera"),
        "ultrasonic": is_fault("front_ultrasonic", "left_ultrasonic", "right_ultrasonic"),
        "metal": is_fault("metal_detector"),
        "network": is_fault("network"),
    }


__all__ = [
    "HEALTHY",
    "WARNING",
    "CRITICAL",
    "DISABLED",
    "NOT_INSTALLED",
    "UNKNOWN",
    "HealthThresholds",
    "ComponentHealth",
    "HardwareHealthSupervisor",
    "generic_faults_from_health",
]

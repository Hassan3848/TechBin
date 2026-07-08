"""
Guarded metal-detector override helper.

The override is inactive unless the explicit feature flag is enabled and a
valid metal detection arrives from configured, healthy hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class MetalOverrideResult:
    active: bool
    category: str | None
    recyclable: bool | None
    expectedSide: str | None
    classificationSource: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "category": self.category,
            "recyclable": self.recyclable,
            "expectedSide": self.expectedSide,
            "classificationSource": self.classificationSource,
            "reason": self.reason,
        }


def evaluate_metal_override(
    reading: Any,
    *,
    hardware_healthy: bool,
    enabled: bool | None = None,
) -> MetalOverrideResult:
    active_flag = settings.device.metal_override_enabled if enabled is None else bool(enabled)
    if not active_flag:
        return MetalOverrideResult(False, None, None, None, None, "metal_override_disabled")

    if not hardware_healthy:
        return MetalOverrideResult(False, None, None, None, None, "metal_hardware_not_healthy")

    data = reading.to_dict() if hasattr(reading, "to_dict") else reading
    if not isinstance(data, dict) or not data.get("valid"):
        return MetalOverrideResult(False, None, None, None, None, "metal_reading_invalid")

    if not data.get("metalDetected"):
        return MetalOverrideResult(False, None, None, None, None, "metal_not_detected")

    return MetalOverrideResult(
        active=True,
        category="metal",
        recyclable=True,
        expectedSide="recyclable",
        classificationSource="metal_sensor",
        reason="metal_detected",
    )


__all__ = ["MetalOverrideResult", "evaluate_metal_override"]

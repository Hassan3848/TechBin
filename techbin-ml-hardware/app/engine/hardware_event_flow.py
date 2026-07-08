"""
TechBin hardware event flow orchestrator.

Purpose:
    Connect front session detection, left/right side detection, and the existing
    disposal event processor.

This is the bridge between hardware evidence and event processing.

Flow:
    1. Capture left/right side baseline.
    2. Check front ultrasonic session detector.
    3. Detect left/right compartment disturbance.
    4. If valid, call process_disposal_event().
    5. Return structured result.

Important product rules:
    - Front session detection alone is NOT a disposal event.
    - Side disturbance alone is NOT a disposal event.
    - Event is processed only when required evidence passes.
    - Camera + ML + side + confidence decide final event acceptance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from app.engine.event_processor import EventProcessingResult, process_disposal_event
from app.logger import get_logger
from app.ml.infer import WasteClassifier
from app.sensors.capacity_monitor import DualCapacityMonitor, DualCapacityMonitorResult
from app.sensors.session_detector import FrontSessionDetector, SessionDetectionResult
from app.sensors.side_detector import DualUltrasonicSideDetector, SideDetectionResult
from app.telemetry.uploader import TelemetryUploader


TelemetryMode = Literal["none", "queue", "dry_run", "upload"]
TelemetryPolicy = Literal["accepted_only", "all_events", "all", "none"]


logger = get_logger(__name__)


HardwareFlowStatus = Literal[
    "processed",
    "no_session",
    "side_detection_failed",
    "event_processing_failed",
    "fault",
]


class HardwareEventFlowError(RuntimeError):
    """Raised when the hardware event flow fails unexpectedly."""


@dataclass(frozen=True)
class HardwareEventFlowConfig:
    """
    Configuration for one hardware event flow run.
    """

    require_session_trigger: bool = True
    require_compartment_confirmation: bool = True
    auto_capture_side_baseline: bool = True
    update_capacity_monitor: bool = False
    source: str = "hardware_event_flow"
    log_prefix: str = "hardware_event"
    telemetry_prefix: str = "hardware_event"
    telemetry_mode: TelemetryMode = "queue"
    telemetry_policy: TelemetryPolicy = "accepted_only"
    fail_on_telemetry_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HardwareEventFlowResult:
    """
    Structured result for one hardware event flow attempt.
    """

    timestamp: str
    status: HardwareFlowStatus
    processed: bool
    message: str
    sessionDetection: dict[str, Any] | None
    sideDetection: dict[str, Any] | None
    capacityMonitor: dict[str, Any] | None
    eventProcessing: dict[str, Any] | None
    payload: dict[str, Any] | None
    logPath: str | None
    telemetry: dict[str, Any] | None
    faultCode: str | None
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _safe_to_dict(value: Any) -> dict[str, Any] | None:
    """
    Convert known result objects to dictionaries safely.
    """

    if value is None:
        return None

    if hasattr(value, "to_dict"):
        return value.to_dict()

    if is_dataclass(value):
        return asdict(value)

    if isinstance(value, dict):
        return value

    return {"value": str(value)}


def _event_result_to_dict(result: EventProcessingResult | None) -> dict[str, Any] | None:
    """
    Convert EventProcessingResult to a safe dictionary.
    """

    if result is None:
        return None

    if hasattr(result, "to_dict"):
        return result.to_dict()

    data: dict[str, Any] = {}

    for field_name in (
        "payload",
        "log_path",
        "telemetry",
        "image_path",
        "inference",
        "validation",
    ):
        if hasattr(result, field_name):
            value = getattr(result, field_name)

            if isinstance(value, Path):
                data[field_name] = str(value)
            elif hasattr(value, "to_dict"):
                data[field_name] = value.to_dict()
            elif is_dataclass(value):
                data[field_name] = asdict(value)
            else:
                data[field_name] = value

    return data


class HardwareEventFlow:
    """
    Orchestrates one TechBin hardware-driven disposal attempt.

    This class does not directly read GPIO itself. It uses the sensor modules
    provided to it. If those modules use simulated backends, this is safe.
    If they use real GPIO backends, real hardware will be used.
    """

    def __init__(
        self,
        *,
        session_detector: FrontSessionDetector,
        side_detector: DualUltrasonicSideDetector,
        classifier: WasteClassifier | None = None,
        capacity_monitor: DualCapacityMonitor | None = None,
        telemetry_uploader: TelemetryUploader | None = None,
        config: HardwareEventFlowConfig | None = None,
    ) -> None:
        self.session_detector = session_detector
        self.side_detector = side_detector
        self.classifier = classifier
        self.capacity_monitor = capacity_monitor
        self.telemetry_uploader = telemetry_uploader
        self.config = config or HardwareEventFlowConfig()

    def capture_side_baseline(self) -> None:
        """
        Capture baseline left/right ultrasonic readings.

        In real use, this should be done before the waste enters a compartment.
        """

        self.side_detector.capture_baseline()

    def process_once(
        self,
        *,
        image_path: str | Path | None = None,
        metal_detected: bool | None = None,
    ) -> HardwareEventFlowResult:
        """
        Run one hardware-driven event attempt.

        This method may return no_session or side_detection_failed without
        creating a disposal event.
        """

        capacity_result: DualCapacityMonitorResult | None = None
        session_result: SessionDetectionResult | None = None
        side_result: SideDetectionResult | None = None
        event_result: EventProcessingResult | None = None

        try:
            if self.config.update_capacity_monitor and self.capacity_monitor is not None:
                capacity_result = self.capacity_monitor.check_all()

            if self.config.auto_capture_side_baseline:
                self.capture_side_baseline()

            session_result = self.session_detector.update()

            if self.config.require_session_trigger and not session_result.sessionActive:
                return HardwareEventFlowResult(
                    timestamp=_now_iso(),
                    status="no_session",
                    processed=False,
                    message="No active front session detected; event processing skipped.",
                    sessionDetection=session_result.to_dict(),
                    sideDetection=None,
                    capacityMonitor=_safe_to_dict(capacity_result),
                    eventProcessing=None,
                    payload=None,
                    logPath=None,
                    telemetry=None,
                    faultCode="no_active_session",
                    config=self.config.to_dict(),
                )

            side_result = self.side_detector.detect_once()

            if self.config.require_compartment_confirmation and not side_result.valid:
                return HardwareEventFlowResult(
                    timestamp=_now_iso(),
                    status="side_detection_failed",
                    processed=False,
                    message="Compartment side could not be confirmed; event processing skipped.",
                    sessionDetection=session_result.to_dict(),
                    sideDetection=side_result.to_dict(),
                    capacityMonitor=_safe_to_dict(capacity_result),
                    eventProcessing=None,
                    payload=None,
                    logPath=None,
                    telemetry=None,
                    faultCode=side_result.faultCode or "side_detection_failed",
                    config=self.config.to_dict(),
                )

            if side_result.disposalSide is None:
                return HardwareEventFlowResult(
                    timestamp=_now_iso(),
                    status="side_detection_failed",
                    processed=False,
                    message="Side detector did not return a usable disposal side.",
                    sessionDetection=session_result.to_dict(),
                    sideDetection=side_result.to_dict(),
                    capacityMonitor=_safe_to_dict(capacity_result),
                    eventProcessing=None,
                    payload=None,
                    logPath=None,
                    telemetry=None,
                    faultCode="disposal_side_missing",
                    config=self.config.to_dict(),
                )

            event_result = process_disposal_event(
                disposal_side=side_result.disposalSide,
                image_path=image_path,
                classifier=self.classifier,
                telemetry_uploader=self.telemetry_uploader,
                source=self.config.source,
                log_prefix=self.config.log_prefix,
                telemetry_prefix=self.config.telemetry_prefix,
                telemetry_mode=self.config.telemetry_mode,
                telemetry_policy=self.config.telemetry_policy,
                fail_on_telemetry_error=self.config.fail_on_telemetry_error,
                session_triggered=session_result.sessionActive,
                compartment_confirmed=side_result.valid,
                metal_detected=metal_detected,
                require_session_trigger=self.config.require_session_trigger,
                require_compartment_confirmation=self.config.require_compartment_confirmation,
            )

            payload = getattr(event_result, "payload", None)
            log_path = getattr(event_result, "log_path", None)
            telemetry = getattr(event_result, "telemetry", None)

            logger.info(
                "Hardware event flow processed | side=%s | accepted=%s | log=%s",
                side_result.disposalSide,
                payload.get("isEventAccepted") if isinstance(payload, dict) else None,
                log_path,
            )

            return HardwareEventFlowResult(
                timestamp=_now_iso(),
                status="processed",
                processed=True,
                message="Hardware event flow processed successfully.",
                sessionDetection=session_result.to_dict(),
                sideDetection=side_result.to_dict(),
                capacityMonitor=_safe_to_dict(capacity_result),
                eventProcessing=_event_result_to_dict(event_result),
                payload=payload,
                logPath=str(log_path) if log_path is not None else None,
                telemetry=telemetry,
                faultCode=None,
                config=self.config.to_dict(),
            )

        except Exception as exc:
            logger.exception("Hardware event flow failed")

            return HardwareEventFlowResult(
                timestamp=_now_iso(),
                status="fault",
                processed=False,
                message=str(exc),
                sessionDetection=_safe_to_dict(session_result),
                sideDetection=_safe_to_dict(side_result),
                capacityMonitor=_safe_to_dict(capacity_result),
                eventProcessing=_event_result_to_dict(event_result),
                payload=None,
                logPath=None,
                telemetry=None,
                faultCode="hardware_event_flow_failed",
                config=self.config.to_dict(),
            )


__all__ = [
    "HardwareFlowStatus",
    "HardwareEventFlowError",
    "HardwareEventFlowConfig",
    "HardwareEventFlowResult",
    "HardwareEventFlow",
]

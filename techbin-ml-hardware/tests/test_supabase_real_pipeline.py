"""
Dry-run tests for the permanent real-device Supabase pipeline.

Run from project root:
    PYTHONPATH=. python3 tests/test_supabase_real_pipeline.py
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import app.engine.real_device_pipeline as real_device_pipeline
from app.engine.real_device_pipeline import (
    RealDeviceDisposalPipeline,
    RealDevicePipelineConfig,
)
from app.ml.effnetv2 import RealPredictionResult
from app.telemetry.supabase import build_heartbeat_payload, build_latest_event
from app.telemetry.totals import LocalTotalsStore
from app.telemetry.uploader import TelemetryUploader, TransportResponse


class StaticTransport:
    def __init__(self, responses: list[TransportResponse]) -> None:
        self.responses = list(responses)
        self.sent_payloads: list[dict] = []

    def send(self, payload: dict) -> TransportResponse:
        self.sent_payloads.append(payload)
        if self.responses:
            return self.responses.pop(0)
        return TransportResponse(ok=True, status_code=200, message="ok")


class DictResult:
    def __init__(self, data: dict) -> None:
        self.data = data

    def to_dict(self) -> dict:
        return self.data


class FakeSessionDetector:
    def update(self) -> DictResult:
        return DictResult({"sessionStarted": True, "sessionActive": True})


class FakeSideDetector:
    def __init__(self, *, side: str | None = "right", valid: bool = True) -> None:
        self.side = side
        self.valid = valid
        self.baseline_captured = False

    def capture_baseline(self) -> None:
        self.baseline_captured = True

    def detect_once(self) -> DictResult:
        detected = self.side if self.valid else "unknown"
        return DictResult(
            {
                "valid": self.valid,
                "detectedSide": detected,
                "disposalSide": self.side if self.valid else None,
                "faultCode": None if self.valid else "no_compartment_disturbance",
            }
        )


class FakeCapacityMonitor:
    def check_all(self) -> dict:
        return {
            "overallValid": True,
            "left": {
                "fillLevel": {
                    "fillPercentage": 38,
                }
            },
            "right": {
                "fillLevel": {
                    "fillPercentage": 61,
                }
            },
        }


class FakeStack:
    def __init__(self, *, side: str | None = "right", side_valid: bool = True) -> None:
        self.session_detector = FakeSessionDetector()
        self.side_detector = FakeSideDetector(side=side, valid=side_valid)
        self.capacity_monitor = FakeCapacityMonitor()


class FakeClassifier:
    def __init__(self, prediction: RealPredictionResult) -> None:
        self.prediction = prediction

    def capture_average_prediction(self, camera) -> RealPredictionResult:
        return self.prediction


class FakeMetalSensor:
    def __init__(
        self,
        *,
        detected: bool | None = False,
        valid: bool = True,
        fault_code: str | None = None,
    ) -> None:
        self.detected = detected
        self.valid = valid
        self.fault_code = fault_code

    def read_debounced(self) -> DictResult:
        return DictResult(
            {
                "sensorName": "metal_sensor",
                "metalDetected": self.detected,
                "rawValues": (
                    [not self.detected] * 5
                    if isinstance(self.detected, bool)
                    else []
                ),
                "valid": self.valid,
                "faultCode": self.fault_code,
                "signalGpio": 21,
                "activeLow": True,
            }
        )


def prediction(
    *,
    category: str = "cardboard",
    confidence: float = 0.91,
    margin: float = 0.20,
    accepted: bool = True,
) -> RealPredictionResult:
    recyclable = category != "trash"
    return RealPredictionResult(
        category=category,
        label=category,
        confidence=confidence,
        margin=margin,
        accepted=accepted,
        rejectionReason=None if accepted else "low_margin:0.050<min:0.120",
        expectedSide="recyclable" if recyclable else "non_recyclable",
        recyclable=recyclable,
        modelVersion="test-model",
        classificationSource="camera",
        inferenceBackend="dry_run",
        inferenceTimeMs=1.0,
        imagePath="/tmp/test.jpg",
        top3=[
            {"label": category, "confidence": confidence},
            {"label": "trash", "confidence": confidence - margin},
        ],
        rawOutput={},
    )


def build_pipeline(
    *,
    tmp: Path,
    side: str | None,
    side_valid: bool,
    pred: RealPredictionResult,
    metal_sensor: FakeMetalSensor | None = None,
    transport: StaticTransport | None = None,
) -> RealDeviceDisposalPipeline:
    uploader = TelemetryUploader(
        transport=transport
        or StaticTransport([TransportResponse(ok=False, status_code=None, message="dry")]),
        queue_root=tmp / "queue",
        max_retries=3,
    )

    return RealDeviceDisposalPipeline(
        hardware_stack=FakeStack(side=side, side_valid=side_valid),
        classifier=FakeClassifier(pred),
        metal_sensor=metal_sensor or FakeMetalSensor(detected=False),
        totals_store=LocalTotalsStore(tmp / "totals.json"),
        telemetry_uploader=uploader,
        config=RealDevicePipelineConfig(
            item_position_seconds=0.0,
            side_confirm_timeout_seconds=0.01,
            side_poll_seconds=0.0,
            telemetry_mode="queue",
        ),
    )


def process_once_with_metal_override(
    pipeline: RealDeviceDisposalPipeline,
    *,
    enabled: bool,
):
    original_settings = real_device_pipeline.settings
    real_device_pipeline.settings = replace(
        original_settings,
        device=replace(
            original_settings.device,
            metal_override_enabled=enabled,
        ),
    )
    try:
        return pipeline.process_once(camera=object())
    finally:
        real_device_pipeline.settings = original_settings


def test_confirmed_recyclable_event(tmp: Path) -> None:
    result = build_pipeline(
        tmp=tmp,
        side="right",
        side_valid=True,
        pred=prediction(category="cardboard"),
    ).process_once(camera=object())

    assert result.status == "processed"
    assert result.metalSensor is not None
    assert result.metalSensor["metalDetected"] is False
    assert result.supabasePayload is not None
    assert result.supabasePayload["latestEvent"]["category"] == "cardboard"
    assert result.supabasePayload["latestEvent"]["correct"] is True
    assert result.totals is not None
    assert result.totals["totalItems"] == 1
    assert result.totals["cardboard"] == 1
    assert result.totals["correctDisposals"] == 1
    assert result.totals["incorrectDisposals"] == 0


def test_metal_false_keeps_camera_category(tmp: Path) -> None:
    result = build_pipeline(
        tmp=tmp,
        side="right",
        side_valid=True,
        pred=prediction(category="plastic_glass"),
        metal_sensor=FakeMetalSensor(detected=False),
    ).process_once(camera=object())

    assert result.status == "processed"
    assert result.metalSensor is not None
    assert result.metalSensor["metalDetected"] is False
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["category"] == "plastic_glass"
    assert event["label"] == "plastic_glass"
    assert event["classificationSource"] == "camera"
    assert event["expectedSide"] == "recyclable"
    assert result.totals is not None
    assert result.totals["plastic_glass"] == 1
    assert result.totals["metal"] == 0


def test_metal_true_override_disabled_keeps_camera_category(tmp: Path) -> None:
    result = process_once_with_metal_override(
        build_pipeline(
            tmp=tmp,
            side="right",
            side_valid=True,
            pred=prediction(category="plastic_glass"),
            metal_sensor=FakeMetalSensor(detected=True),
        ),
        enabled=False,
    )

    assert result.status == "processed"
    assert result.metalSensor is not None
    assert result.metalSensor["metalDetected"] is True
    assert result.prediction is not None
    assert result.prediction["category"] == "plastic_glass"
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["category"] == "plastic_glass"
    assert event["label"] == "plastic_glass"
    assert event["classificationSource"] == "camera"
    assert result.totals is not None
    assert result.totals["plastic_glass"] == 1
    assert result.totals["metal"] == 0


def test_metal_true_override_enabled_overrides_plastic_glass_to_metal(tmp: Path) -> None:
    result = process_once_with_metal_override(
        build_pipeline(
            tmp=tmp,
            side="right",
            side_valid=True,
            pred=prediction(category="plastic_glass"),
            metal_sensor=FakeMetalSensor(detected=True),
        ),
        enabled=True,
    )

    assert result.status == "processed"
    assert result.metalSensor is not None
    assert result.metalSensor["metalDetected"] is True
    assert result.prediction is not None
    assert result.prediction["category"] == "plastic_glass"
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["category"] == "metal"
    assert event["label"] == "metal"
    assert event["classificationSource"] == "metal_sensor"
    assert event["expectedSide"] == "recyclable"
    assert event["correct"] is True
    assert result.totals is not None
    assert result.totals["plastic_glass"] == 0
    assert result.totals["metal"] == 1


def test_metal_false_override_enabled_keeps_camera_category(tmp: Path) -> None:
    result = process_once_with_metal_override(
        build_pipeline(
            tmp=tmp,
            side="right",
            side_valid=True,
            pred=prediction(category="plastic_glass"),
            metal_sensor=FakeMetalSensor(detected=False),
        ),
        enabled=True,
    )

    assert result.status == "processed"
    assert result.metalSensor is not None
    assert result.metalSensor["metalDetected"] is False
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["category"] == "plastic_glass"
    assert event["label"] == "plastic_glass"
    assert event["classificationSource"] == "camera"
    assert result.totals is not None
    assert result.totals["plastic_glass"] == 1
    assert result.totals["metal"] == 0


def test_metal_true_overrides_plastic_glass_to_metal(tmp: Path) -> None:
    result = process_once_with_metal_override(
        build_pipeline(
            tmp=tmp,
            side="right",
            side_valid=True,
            pred=prediction(category="plastic_glass"),
            metal_sensor=FakeMetalSensor(detected=True),
        ),
        enabled=True,
    )

    assert result.status == "processed"
    assert result.metalSensor is not None
    assert result.metalSensor["metalDetected"] is True
    assert result.prediction is not None
    assert result.prediction["category"] == "plastic_glass"
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["category"] == "metal"
    assert event["label"] == "metal"
    assert event["classificationSource"] == "metal_sensor"
    assert event["expectedSide"] == "recyclable"
    assert event["correct"] is True
    assert result.totals is not None
    assert result.totals["plastic_glass"] == 0
    assert result.totals["metal"] == 1


def test_metal_true_overrides_cardboard_to_metal(tmp: Path) -> None:
    result = process_once_with_metal_override(
        build_pipeline(
            tmp=tmp,
            side="right",
            side_valid=True,
            pred=prediction(category="cardboard"),
            metal_sensor=FakeMetalSensor(detected=True),
        ),
        enabled=True,
    )

    assert result.status == "processed"
    assert result.prediction is not None
    assert result.prediction["category"] == "cardboard"
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["category"] == "metal"
    assert event["classificationSource"] == "metal_sensor"
    assert event["expectedSide"] == "recyclable"
    assert result.totals is not None
    assert result.totals["cardboard"] == 0
    assert result.totals["metal"] == 1


def test_invalid_metal_reading_keeps_camera_category(tmp: Path) -> None:
    result = process_once_with_metal_override(
        build_pipeline(
            tmp=tmp,
            side="right",
            side_valid=True,
            pred=prediction(category="plastic_glass"),
            metal_sensor=FakeMetalSensor(
                detected=None,
                valid=False,
                fault_code="forced_invalid",
            ),
        ),
        enabled=True,
    )

    assert result.status == "processed"
    assert result.metalSensor is not None
    assert result.metalSensor["valid"] is False
    assert result.metalSensor["faultCode"] == "forced_invalid"
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["category"] == "plastic_glass"
    assert event["classificationSource"] == "camera"
    assert result.totals is not None
    assert result.totals["plastic_glass"] == 1
    assert result.totals["metal"] == 0


def test_confirmed_incorrect_disposal(tmp: Path) -> None:
    result = build_pipeline(
        tmp=tmp,
        side="left",
        side_valid=True,
        pred=prediction(category="cardboard"),
    ).process_once(camera=object())

    assert result.status == "processed"
    assert result.supabasePayload is not None
    event = result.supabasePayload["latestEvent"]
    assert event["expectedSide"] == "recyclable"
    assert event["disposedSide"] == "non_recyclable"
    assert event["correct"] is False
    assert result.totals is not None
    assert result.totals["incorrectDisposals"] == 1


def test_uncertain_prediction_does_not_update_totals(tmp: Path) -> None:
    result = build_pipeline(
        tmp=tmp,
        side="right",
        side_valid=True,
        pred=prediction(category="cardboard", accepted=False, margin=0.05),
    ).process_once(camera=object())

    assert result.status == "uncertain_prediction"
    assert result.supabasePayload is None
    assert result.totals is None
    assert not (tmp / "totals.json").exists()


def test_unconfirmed_side_does_not_update_totals(tmp: Path) -> None:
    result = build_pipeline(
        tmp=tmp,
        side=None,
        side_valid=False,
        pred=prediction(category="paper"),
    ).process_once(camera=object())

    assert result.status == "side_unconfirmed"
    assert result.supabasePayload is None
    assert result.totals is None
    assert not (tmp / "totals.json").exists()


def test_duplicate_queue_retry_preserves_event_id(tmp: Path) -> None:
    event_id = "pi-BIN-001-test-duplicate"
    payload = {
        "orgId": "techbin",
        "binCode": "BIN-001",
        "status": {"state": "normal", "message": "Running"},
        "sensors": {"leftFillLevel": 1, "rightFillLevel": 2, "fillLevel": 2},
        "statistics": {},
        "faults": {},
        "latestEvent": build_latest_event(
            event_id=event_id,
            category="paper",
            disposed_side="recyclable",
            confidence=0.9,
            model_version="test-model",
        ),
    }

    transport = StaticTransport(
        [
            TransportResponse(ok=False, status_code=None, message="offline"),
            TransportResponse(ok=True, status_code=200, message="sent"),
        ]
    )
    uploader = TelemetryUploader(
        transport=transport,
        queue_root=tmp / "queue",
        max_retries=3,
    )

    first = uploader.upload_or_queue(
        payload,
        prefix="supabase_event",
        payload_id=event_id,
    )
    assert first.status == "queued"
    assert first.payload_id == event_id

    pending_files = list((tmp / "queue" / "pending").glob("*.json"))
    assert len(pending_files) == 1

    queued = json.loads(pending_files[0].read_text(encoding="utf-8"))
    assert queued["payloadId"] == event_id
    assert queued["payload"]["latestEvent"]["eventId"] == event_id

    retry_results = uploader.upload_pending()
    assert retry_results[0].status == "sent"
    assert retry_results[0].payload_id == event_id

    sent_files = list((tmp / "queue" / "sent").glob("*.json"))
    assert len(sent_files) == 1
    sent = json.loads(sent_files[0].read_text(encoding="utf-8"))
    assert sent["payloadId"] == event_id
    assert sent["payload"]["latestEvent"]["eventId"] == event_id


def test_heartbeat_has_no_latest_event() -> None:
    payload = build_heartbeat_payload(
        statistics={"totalItems": 3, "paper": 1},
        sensors={"leftFillLevel": 38, "rightFillLevel": 61, "fillLevel": 61},
        status_message="Heartbeat",
    )

    assert "latestEvent" not in payload
    assert payload["status"]["message"] == "Heartbeat"
    assert payload["sensors"]["leftFillLevel"] == 38


def main() -> None:
    with TemporaryDirectory(prefix="techbin_supabase_tests_") as tmpdir:
        tmp = Path(tmpdir)
        test_confirmed_recyclable_event(tmp / "confirmed_recyclable")
        test_metal_false_keeps_camera_category(tmp / "metal_false")
        test_metal_true_override_disabled_keeps_camera_category(
            tmp / "metal_true_disabled"
        )
        test_metal_true_override_enabled_overrides_plastic_glass_to_metal(
            tmp / "metal_true_enabled"
        )
        test_metal_false_override_enabled_keeps_camera_category(
            tmp / "metal_false_enabled"
        )
        test_metal_true_overrides_plastic_glass_to_metal(tmp / "metal_true_plastic")
        test_metal_true_overrides_cardboard_to_metal(tmp / "metal_true_cardboard")
        test_invalid_metal_reading_keeps_camera_category(tmp / "metal_invalid")
        test_confirmed_incorrect_disposal(tmp / "incorrect")
        test_uncertain_prediction_does_not_update_totals(tmp / "uncertain")
        test_unconfirmed_side_does_not_update_totals(tmp / "unconfirmed")
        test_duplicate_queue_retry_preserves_event_id(tmp / "duplicate")
        test_heartbeat_has_no_latest_event()

    print("All Supabase real pipeline dry-run tests passed.")


if __name__ == "__main__":
    main()

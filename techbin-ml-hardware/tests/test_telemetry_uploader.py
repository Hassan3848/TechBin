"""
Test TechBin telemetry uploader.

This test uses DryRunTransport, so it does not contact any real backend.

Run from project root:
    PYTHONPATH=. python3 tests/test_telemetry_uploader.py
"""

from __future__ import annotations

from datetime import datetime
import json
import shutil
from pathlib import Path
from pprint import pprint

from app.telemetry.payloads import build_disposal_event_payload
from app.telemetry.uploader import DryRunTransport, TelemetryUploader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_QUEUE_ROOT = PROJECT_ROOT / "logs" / "telemetry_queue_test"


def reset_test_queue() -> None:
    if TEST_QUEUE_ROOT.exists():
        shutil.rmtree(TEST_QUEUE_ROOT)


def build_sample_payload() -> dict:
    return build_disposal_event_payload(
        predicted_class="plastic",
        confidence=0.91,
        image_path="/home/hassan/techbin-device/captures/test.jpg",
        disposal_side="right",
        source="telemetry_uploader_test",
    )


def test_pending_retry_repairs_hardware_health_last_checked_at() -> None:
    reset_test_queue()

    uploader = TelemetryUploader(
        transport=DryRunTransport(),
        queue_root=TEST_QUEUE_ROOT,
        max_retries=3,
    )
    event_id = "test-event-1"
    payload = {
        "eventType": "bin_state",
        "latestEvent": {"eventId": event_id},
        "hardwareHealth": {
            "telemetryQueue": {
                "componentId": "telemetry_queue",
                "lastCheckedAt": None,
                "lastSuccessAt": None,
            }
        },
    }

    queue_path = uploader.enqueue(payload, prefix="supabase_event", payload_id=event_id)
    result = uploader.upload_pending_file(queue_path)

    assert result.status == "sent"
    assert result.payload_id == event_id

    sent_files = list((TEST_QUEUE_ROOT / "sent").glob("*.json"))
    assert len(sent_files) == 1
    sent = json.loads(sent_files[0].read_text(encoding="utf-8"))
    assert sent["payloadId"] == event_id
    assert sent["payload"]["latestEvent"]["eventId"] == event_id
    datetime.fromisoformat(sent["payload"]["hardwareHealth"]["telemetryQueue"]["lastCheckedAt"])
    assert sent["payload"]["hardwareHealth"]["telemetryQueue"]["lastSuccessAt"] is None


def main() -> None:
    reset_test_queue()

    uploader = TelemetryUploader(
        transport=DryRunTransport(),
        queue_root=TEST_QUEUE_ROOT,
        max_retries=3,
    )

    payload = build_sample_payload()

    print()
    print("========== Direct Dry-Run Upload ==========")
    direct_result = uploader.upload_payload(payload)
    pprint(direct_result.to_dict())

    assert direct_result.status == "sent"
    assert direct_result.response_status_code == 200

    print("PASS: direct dry-run upload")

    print()
    print("========== Queue Payload ==========")
    queue_path = uploader.enqueue(payload, prefix="test_payload")
    print("Queued:", queue_path)

    assert queue_path.exists()
    assert queue_path.parent.name == "pending"

    print("PASS: queue payload")

    print()
    print("========== Upload Pending ==========")
    results = uploader.upload_pending()

    for result in results:
        pprint(result.to_dict())

    assert len(results) == 1
    assert results[0].status == "sent"

    sent_files = list((TEST_QUEUE_ROOT / "sent").glob("*.json"))
    pending_files = list((TEST_QUEUE_ROOT / "pending").glob("*.json"))

    assert len(sent_files) == 1
    assert len(pending_files) == 0

    print("PASS: upload pending")

    test_pending_retry_repairs_hardware_health_last_checked_at()
    print("PASS: pending retry repairs hardware health timestamps")

    print()
    print("All telemetry uploader tests passed.")


if __name__ == "__main__":
    main()

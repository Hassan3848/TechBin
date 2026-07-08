"""
Test TechBin hardware event flow without touching GPIO.

This test uses:
    - simulated front ultrasonic session detector
    - simulated left/right ultrasonic side detector
    - mock ML classifier
    - existing event processor
    - local JSON logs and telemetry queue

Run:
    PYTHONPATH=. python3 tests/test_hardware_event_flow.py
"""

from __future__ import annotations

from pathlib import Path
from pprint import pprint

from PIL import Image

from app.engine.hardware_event_flow import HardwareEventFlow, HardwareEventFlowConfig
from app.ml.infer import create_mock_classifier
from app.sensors.pin_map import PIN_MAP, validate_pin_map
from app.sensors.session_detector import FrontSessionDetector, SessionDetectorConfig
from app.sensors.side_detector import DualUltrasonicSideDetector, SideDetectionConfig
from app.sensors.ultrasonic import SimulatedUltrasonicBackend, build_sensor_from_pin_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_IMAGE = PROJECT_ROOT / "captures" / "hardware_event_flow_test.jpg"


def ensure_test_image() -> Path:
    TEST_IMAGE.parent.mkdir(parents=True, exist_ok=True)

    if not TEST_IMAGE.exists():
        image = Image.new("RGB", (224, 224), color=(120, 120, 120))
        image.save(TEST_IMAGE, format="JPEG")

    return TEST_IMAGE


def build_session_detector_for_active_session() -> FrontSessionDetector:
    front_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_front,
        enabled=True,
        backend=SimulatedUltrasonicBackend(fixed_distance_cm=25.0),
        samples=1,
    )

    return FrontSessionDetector(
        front_sensor,
        config=SessionDetectorConfig(
            presence_threshold_cm=35.0,
            stable_presence_reads=1,
            stable_absence_reads=2,
        ),
    )


def build_session_detector_for_no_session() -> FrontSessionDetector:
    front_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_front,
        enabled=True,
        backend=SimulatedUltrasonicBackend(fixed_distance_cm=100.0),
        samples=1,
    )

    return FrontSessionDetector(
        front_sensor,
        config=SessionDetectorConfig(
            presence_threshold_cm=35.0,
            stable_presence_reads=1,
            stable_absence_reads=2,
        ),
    )


def build_side_detector_left_disturbed() -> DualUltrasonicSideDetector:
    left_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_left,
        enabled=True,
        backend=SimulatedUltrasonicBackend(
            sequence_cm=[
                45.0,
                30.0,
            ],
        ),
        samples=1,
    )

    right_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_right,
        enabled=True,
        backend=SimulatedUltrasonicBackend(
            sequence_cm=[
                45.0,
                44.0,
            ],
        ),
        samples=1,
    )

    return DualUltrasonicSideDetector(
        left_sensor=left_sensor,
        right_sensor=right_sensor,
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )


def build_side_detector_right_disturbed() -> DualUltrasonicSideDetector:
    left_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_left,
        enabled=True,
        backend=SimulatedUltrasonicBackend(
            sequence_cm=[
                45.0,
                44.0,
            ],
        ),
        samples=1,
    )

    right_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_right,
        enabled=True,
        backend=SimulatedUltrasonicBackend(
            sequence_cm=[
                45.0,
                28.0,
            ],
        ),
        samples=1,
    )

    return DualUltrasonicSideDetector(
        left_sensor=left_sensor,
        right_sensor=right_sensor,
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )


def build_side_detector_ambiguous() -> DualUltrasonicSideDetector:
    left_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_left,
        enabled=True,
        backend=SimulatedUltrasonicBackend(
            sequence_cm=[
                45.0,
                30.0,
            ],
        ),
        samples=1,
    )

    right_sensor = build_sensor_from_pin_config(
        PIN_MAP.ultrasonic_right,
        enabled=True,
        backend=SimulatedUltrasonicBackend(
            sequence_cm=[
                45.0,
                31.0,
            ],
        ),
        samples=1,
    )

    return DualUltrasonicSideDetector(
        left_sensor=left_sensor,
        right_sensor=right_sensor,
        config=SideDetectionConfig(
            disturbance_threshold_cm=5.0,
            dominance_margin_cm=6.0,
        ),
    )


def test_left_trash_event_processed() -> None:
    print()
    print("========== Hardware Flow: Left Trash Event Processed ==========")

    validate_pin_map()
    image_path = ensure_test_image()

    classifier = create_mock_classifier(
        predicted_class="trash",
        confidence=0.88,
    )

    flow = HardwareEventFlow(
        session_detector=build_session_detector_for_active_session(),
        side_detector=build_side_detector_left_disturbed(),
        classifier=classifier,
        config=HardwareEventFlowConfig(
            require_session_trigger=True,
            require_compartment_confirmation=True,
            source="test_hardware_flow_left_trash",
            log_prefix="test_hardware_flow_left_trash",
            telemetry_prefix="test_hardware_flow_left_trash",
            telemetry_mode="queue",
            telemetry_policy="accepted_only",
        ),
    )

    result = flow.process_once(image_path=image_path)

    pprint(result.to_dict())

    assert result.status == "processed"
    assert result.processed is True
    assert result.payload is not None
    assert result.payload["predictedClass"] == "trash"
    assert result.payload["disposalSide"] == "left"
    assert result.payload["expectedSide"] == "left"
    assert result.payload["isCorrectDisposal"] is True
    assert result.payload["isEventAccepted"] is True
    assert result.logPath is not None
    assert Path(result.logPath).exists()

    print("PASS: left trash event processed")


def test_right_plastic_event_processed() -> None:
    print()
    print("========== Hardware Flow: Right Plastic Event Processed ==========")

    image_path = ensure_test_image()

    classifier = create_mock_classifier(
        predicted_class="plastic",
        confidence=0.91,
    )

    flow = HardwareEventFlow(
        session_detector=build_session_detector_for_active_session(),
        side_detector=build_side_detector_right_disturbed(),
        classifier=classifier,
        config=HardwareEventFlowConfig(
            require_session_trigger=True,
            require_compartment_confirmation=True,
            source="test_hardware_flow_right_plastic",
            log_prefix="test_hardware_flow_right_plastic",
            telemetry_prefix="test_hardware_flow_right_plastic",
            telemetry_mode="queue",
            telemetry_policy="accepted_only",
        ),
    )

    result = flow.process_once(image_path=image_path)

    pprint(result.to_dict())

    assert result.status == "processed"
    assert result.processed is True
    assert result.payload is not None
    assert result.payload["predictedClass"] == "plastic"
    assert result.payload["disposalSide"] == "right"
    assert result.payload["expectedSide"] == "right"
    assert result.payload["isCorrectDisposal"] is True
    assert result.payload["isEventAccepted"] is True

    print("PASS: right plastic event processed")


def test_no_session_skips_event() -> None:
    print()
    print("========== Hardware Flow: No Session Skips Event ==========")

    image_path = ensure_test_image()

    classifier = create_mock_classifier(
        predicted_class="plastic",
        confidence=0.91,
    )

    flow = HardwareEventFlow(
        session_detector=build_session_detector_for_no_session(),
        side_detector=build_side_detector_right_disturbed(),
        classifier=classifier,
        config=HardwareEventFlowConfig(
            require_session_trigger=True,
            require_compartment_confirmation=True,
            source="test_hardware_flow_no_session",
            log_prefix="test_hardware_flow_no_session",
            telemetry_prefix="test_hardware_flow_no_session",
        ),
    )

    result = flow.process_once(image_path=image_path)

    pprint(result.to_dict())

    assert result.status == "no_session"
    assert result.processed is False
    assert result.payload is None
    assert result.logPath is None
    assert result.faultCode == "no_active_session"

    print("PASS: no session skips event")


def test_ambiguous_side_skips_event() -> None:
    print()
    print("========== Hardware Flow: Ambiguous Side Skips Event ==========")

    image_path = ensure_test_image()

    classifier = create_mock_classifier(
        predicted_class="plastic",
        confidence=0.91,
    )

    flow = HardwareEventFlow(
        session_detector=build_session_detector_for_active_session(),
        side_detector=build_side_detector_ambiguous(),
        classifier=classifier,
        config=HardwareEventFlowConfig(
            require_session_trigger=True,
            require_compartment_confirmation=True,
            source="test_hardware_flow_ambiguous_side",
            log_prefix="test_hardware_flow_ambiguous_side",
            telemetry_prefix="test_hardware_flow_ambiguous_side",
        ),
    )

    result = flow.process_once(image_path=image_path)

    pprint(result.to_dict())

    assert result.status == "side_detection_failed"
    assert result.processed is False
    assert result.payload is None
    assert result.logPath is None
    assert result.faultCode == "ambiguous_compartment_disturbance"

    print("PASS: ambiguous side skips event")


def main() -> None:
    test_left_trash_event_processed()
    test_right_plastic_event_processed()
    test_no_session_skips_event()
    test_ambiguous_side_skips_event()

    print()
    print("All hardware event flow tests passed.")


if __name__ == "__main__":
    main()

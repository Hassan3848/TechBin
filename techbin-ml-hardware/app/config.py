"""
TechBin device runtime configuration.

This module contains production-style settings for the Raspberry Pi runtime.
All other modules should read shared constants from here instead of hardcoding
paths, bin IDs, confidence thresholds, class names, or side rules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

CAPTURES_DIR: Final[Path] = PROJECT_ROOT / "captures"
LOGS_DIR: Final[Path] = PROJECT_ROOT / "logs"
MODELS_DIR: Final[Path] = PROJECT_ROOT / "models"


def _strip_env_quotes(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        return cleaned[1:-1]
    return cleaned


def _load_local_env_file() -> None:
    """
    Load local Pi runtime settings from a Git-ignored env file.

    Existing process environment values win. This keeps deployment managers and
    systemd EnvironmentFile settings authoritative while still supporting a
    local, reboot-persistent file for the Pi.
    """

    env_path = Path(os.getenv("TECHBIN_LOCAL_ENV_FILE", PROJECT_ROOT / ".env.local")).expanduser()
    if not env_path.exists():
        return

    try:
        if env_path.stat().st_mode & 0o077:
            raise RuntimeError(f"{env_path} must be permission mode 600")

        with env_path.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                name, value = line.split("=", 1)
                name = name.strip()
                if not name or name in os.environ:
                    continue

                os.environ[name] = _strip_env_quotes(value)

    except Exception as exc:
        raise RuntimeError(f"Failed to load local env file {env_path}") from exc


_load_local_env_file()


# ---------------------------------------------------------------------
# Device identity
# ---------------------------------------------------------------------

DEFAULT_BIN_ID: Final[str] = "TECHBIN-001"
DEFAULT_ORG_ID: Final[str] = "techbin"


# ---------------------------------------------------------------------
# Waste classes and disposal rules
# ---------------------------------------------------------------------

WASTE_CLASSES: Final[tuple[str, ...]] = (
    "cardboard",
    "glass",
    "metal",
    "paper",
    "plastic",
    "trash",
)

RECYCLABLE_CLASSES: Final[tuple[str, ...]] = (
    "cardboard",
    "glass",
    "metal",
    "paper",
    "plastic",
)

NON_RECYCLABLE_CLASSES: Final[tuple[str, ...]] = (
    "trash",
)

RECYCLABLE: Final[str] = "recyclable"
NON_RECYCLABLE: Final[str] = "non-recyclable"

RIGHT_SIDE: Final[str] = "right"
LEFT_SIDE: Final[str] = "left"

CATEGORY_TO_EXPECTED_SIDE: Final[dict[str, str]] = {
    RECYCLABLE: RIGHT_SIDE,
    NON_RECYCLABLE: LEFT_SIDE,
}


# ---------------------------------------------------------------------
# Runtime settings
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class CameraSettings:
    image_width: int = 1280
    image_height: int = 720
    warmup_seconds: float = 1.0
    filename_prefix: str = "event"


@dataclass(frozen=True)
class MLSettings:
    min_confidence: float = 0.70
    low_confidence_action: str = "reject"
    mock_class: str = "plastic"
    mock_confidence: float = 0.91
    model_package_path: str = ""
    model_version: str = "techbin-effnetv2-v1"
    real_min_confidence: float = 0.60
    real_min_margin: float = 0.12


@dataclass(frozen=True)
class LoggingSettings:
    log_level: str = "INFO"
    log_file_name: str = "techbin_runtime.log"
    event_file_prefix: str = "event"


@dataclass(frozen=True)
class DeviceSettings:
    bin_id: str
    org_id: str
    metal_override_enabled: bool = False


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    bin_code: str
    device_token: str
    timeout_seconds: float


@dataclass(frozen=True)
class HealthSettings:
    detailed_telemetry_enabled: bool = False
    heartbeat_enabled: bool = False
    ultrasonic_warning_failures: int = 2
    ultrasonic_critical_failures: int = 3
    ultrasonic_recovery_successes: int = 2
    queue_warning_pending: int = 10
    queue_critical_pending: int = 100


@dataclass(frozen=True)
class VoiceFeedbackSettings:
    enabled: bool = False
    backend: str = "disabled"
    audio_dir: str = ""
    player_command: str = ""


@dataclass(frozen=True)
class AppSettings:
    project_root: Path
    captures_dir: Path
    logs_dir: Path
    models_dir: Path
    camera: CameraSettings
    ml: MLSettings
    logging: LoggingSettings
    device: DeviceSettings
    supabase: SupabaseSettings
    health: HealthSettings
    voice_feedback: VoiceFeedbackSettings


def _get_env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default

    try:
        return float(value)
    except ValueError:
        return default


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default

    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False

    return default


def load_settings() -> AppSettings:
    """
    Load application settings.

    Environment variables can override important runtime values later without
    changing source code.
    """

    camera_settings = CameraSettings(
        image_width=_get_env_int("TECHBIN_CAMERA_WIDTH", 1280),
        image_height=_get_env_int("TECHBIN_CAMERA_HEIGHT", 720),
        warmup_seconds=_get_env_float("TECHBIN_CAMERA_WARMUP_SECONDS", 1.0),
        filename_prefix=_get_env_str("TECHBIN_CAMERA_FILENAME_PREFIX", "event"),
    )

    ml_settings = MLSettings(
        min_confidence=_get_env_float("TECHBIN_MIN_CONFIDENCE", 0.70),
        low_confidence_action=_get_env_str("TECHBIN_LOW_CONFIDENCE_ACTION", "reject"),
        mock_class=_get_env_str("TECHBIN_MOCK_CLASS", "plastic"),
        mock_confidence=_get_env_float("TECHBIN_MOCK_CONFIDENCE", 0.91),
        model_package_path=_get_env_str("TECHBIN_MODEL_PACKAGE_PATH", ""),
        model_version=_get_env_str("TECHBIN_MODEL_VERSION", "techbin-effnetv2-v1"),
        real_min_confidence=_get_env_float("TECHBIN_REAL_MIN_CONFIDENCE", 0.60),
        real_min_margin=_get_env_float("TECHBIN_REAL_MIN_MARGIN", 0.12),
    )

    logging_settings = LoggingSettings(
        log_level=_get_env_str("TECHBIN_LOG_LEVEL", "INFO"),
        log_file_name=_get_env_str("TECHBIN_LOG_FILE_NAME", "techbin_runtime.log"),
        event_file_prefix=_get_env_str("TECHBIN_EVENT_FILE_PREFIX", "event"),
    )

    device_settings = DeviceSettings(
        bin_id=_get_env_str("TECHBIN_BIN_ID", DEFAULT_BIN_ID),
        org_id=_get_env_str("TECHBIN_ORG_ID", DEFAULT_ORG_ID),
        metal_override_enabled=_get_env_bool(
            "TECHBIN_ENABLE_METAL_OVERRIDE",
            False,
        ),
    )

    supabase_settings = SupabaseSettings(
        url=_get_env_str("TECHBIN_SUPABASE_URL", ""),
        bin_code=_get_env_str("TECHBIN_BIN_CODE", "BIN-001"),
        device_token=_get_env_str("TECHBIN_DEVICE_TOKEN", ""),
        timeout_seconds=_get_env_float("TECHBIN_SUPABASE_TIMEOUT_SECONDS", 10.0),
    )

    health_settings = HealthSettings(
        detailed_telemetry_enabled=_get_env_bool(
            "TECHBIN_ENABLE_DETAILED_HEALTH_TELEMETRY",
            False,
        ),
        heartbeat_enabled=_get_env_bool(
            "TECHBIN_ENABLE_HEALTH_HEARTBEAT",
            False,
        ),
        ultrasonic_warning_failures=_get_env_int(
            "TECHBIN_HEALTH_ULTRASONIC_WARNING_FAILURES",
            2,
        ),
        ultrasonic_critical_failures=_get_env_int(
            "TECHBIN_HEALTH_ULTRASONIC_CRITICAL_FAILURES",
            3,
        ),
        ultrasonic_recovery_successes=_get_env_int(
            "TECHBIN_HEALTH_ULTRASONIC_RECOVERY_SUCCESSES",
            2,
        ),
        queue_warning_pending=_get_env_int(
            "TECHBIN_HEALTH_QUEUE_WARNING_PENDING",
            10,
        ),
        queue_critical_pending=_get_env_int(
            "TECHBIN_HEALTH_QUEUE_CRITICAL_PENDING",
            100,
        ),
    )

    voice_feedback_settings = VoiceFeedbackSettings(
        enabled=_get_env_bool("TECHBIN_ENABLE_VOICE_FEEDBACK", False),
        backend=_get_env_str("TECHBIN_VOICE_FEEDBACK_BACKEND", "disabled"),
        audio_dir=_get_env_str("TECHBIN_VOICE_AUDIO_DIR", ""),
        player_command=_get_env_str("TECHBIN_VOICE_PLAYER_COMMAND", ""),
    )

    return AppSettings(
        project_root=PROJECT_ROOT,
        captures_dir=CAPTURES_DIR,
        logs_dir=LOGS_DIR,
        models_dir=MODELS_DIR,
        camera=camera_settings,
        ml=ml_settings,
        logging=logging_settings,
        device=device_settings,
        supabase=supabase_settings,
        health=health_settings,
        voice_feedback=voice_feedback_settings,
    )


settings: Final[AppSettings] = load_settings()


def ensure_runtime_directories() -> None:
    """
    Create runtime directories if they do not already exist.
    """

    settings.captures_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)


# Keep these aliases for compatibility with older prototype files.
BIN_ID: Final[str] = settings.device.bin_id
ORG_ID: Final[str] = settings.device.org_id

CAMERA_IMAGE_WIDTH: Final[int] = settings.camera.image_width
CAMERA_IMAGE_HEIGHT: Final[int] = settings.camera.image_height
CAMERA_WARMUP_SECONDS: Final[float] = settings.camera.warmup_seconds

MIN_CONFIDENCE: Final[float] = settings.ml.min_confidence


__all__ = [
    "PROJECT_ROOT",
    "CAPTURES_DIR",
    "LOGS_DIR",
    "MODELS_DIR",
    "BIN_ID",
    "ORG_ID",
    "WASTE_CLASSES",
    "RECYCLABLE_CLASSES",
    "NON_RECYCLABLE_CLASSES",
    "RECYCLABLE",
    "NON_RECYCLABLE",
    "RIGHT_SIDE",
    "LEFT_SIDE",
    "CATEGORY_TO_EXPECTED_SIDE",
    "CAMERA_IMAGE_WIDTH",
    "CAMERA_IMAGE_HEIGHT",
    "CAMERA_WARMUP_SECONDS",
    "MIN_CONFIDENCE",
    "SupabaseSettings",
    "settings",
    "ensure_runtime_directories",
]

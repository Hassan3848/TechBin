import { Camera, Radio, ServerCrash, Volume2, Wifi, Zap } from "lucide-react";
import type React from "react";

export const hardwareHealthComponentKeys = [
  "frontUltrasonic",
  "leftUltrasonic",
  "rightUltrasonic",
  "camera",
  "network",
  "metalDetector",
  "voiceFeedback",
  "telemetryQueue",
] as const;

export type HardwareHealthComponentKey = (typeof hardwareHealthComponentKeys)[number];
export type HardwareHealthStatus = "healthy" | "warning" | "critical" | "disabled" | "not_installed" | "unknown";
export type HardwareHealthOverallStatus = "healthy" | "warning" | "critical" | "unknown";

export type HardwareHealthComponent = {
  componentId: string;
  displayName: string;
  status: HardwareHealthStatus;
  faultCode: string | null;
  message: string;
  consecutiveFailures: number;
  consecutiveSuccesses: number;
  lastCheckedAt: string;
  lastSuccessAt: string | null;
};

export type HardwareHealthSnapshot = Record<HardwareHealthComponentKey, HardwareHealthComponent>;

export type BinHardwareHealth = {
  components: HardwareHealthSnapshot | null;
  overallStatus: HardwareHealthOverallStatus;
  receivedAt: string | null;
  deviceLastCheckedAt: string | null;
  deviceLastSuccessAt: string | null;
  lastSeen: string | null;
};

export type HardwareHealthDisplay = {
  key: HardwareHealthComponentKey;
  label: string;
  status: HardwareHealthStatus;
  statusLabel: string;
  message: string;
  faultCode: string | null;
  lastCheckedAt: string | null;
  lastSuccessAt: string | null;
  icon: React.ElementType;
};

const componentDefaults: Record<HardwareHealthComponentKey, { label: string; componentId: string; icon: React.ElementType }> = {
  frontUltrasonic: { label: "Front Ultrasonic", componentId: "front_ultrasonic", icon: Radio },
  leftUltrasonic: { label: "Left Ultrasonic", componentId: "left_ultrasonic", icon: Radio },
  rightUltrasonic: { label: "Right Ultrasonic", componentId: "right_ultrasonic", icon: Radio },
  camera: { label: "Camera", componentId: "camera", icon: Camera },
  network: { label: "Network", componentId: "network", icon: Wifi },
  metalDetector: { label: "Metal Detector", componentId: "metal_detector", icon: Zap },
  voiceFeedback: { label: "Voice Feedback", componentId: "voice_feedback", icon: Volume2 },
  telemetryQueue: { label: "Telemetry Queue", componentId: "telemetry_queue", icon: ServerCrash },
};

export function statusLabel(status: HardwareHealthStatus | HardwareHealthOverallStatus) {
  return status.replace("_", " ").replace(/^./, (char) => char.toUpperCase());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isHealthStatus(value: unknown): value is HardwareHealthStatus {
  return typeof value === "string" && ["healthy", "warning", "critical", "disabled", "not_installed", "unknown"].includes(value);
}

export function parseHardwareHealthSnapshot(value: unknown): HardwareHealthSnapshot | null {
  if (!isRecord(value)) return null;

  const snapshot = {} as HardwareHealthSnapshot;
  for (const key of hardwareHealthComponentKeys) {
    const raw = value[key];
    const defaults = componentDefaults[key];
    if (!isRecord(raw) || !isHealthStatus(raw.status)) return null;
    snapshot[key] = {
      componentId: typeof raw.componentId === "string" ? raw.componentId : defaults.componentId,
      displayName: typeof raw.displayName === "string" && raw.displayName.trim() ? raw.displayName : defaults.label,
      status: raw.status,
      faultCode: typeof raw.faultCode === "string" ? raw.faultCode : null,
      message: typeof raw.message === "string" ? raw.message : "No component message received.",
      consecutiveFailures: typeof raw.consecutiveFailures === "number" ? raw.consecutiveFailures : 0,
      consecutiveSuccesses: typeof raw.consecutiveSuccesses === "number" ? raw.consecutiveSuccesses : 0,
      lastCheckedAt: typeof raw.lastCheckedAt === "string" ? raw.lastCheckedAt : "",
      lastSuccessAt: typeof raw.lastSuccessAt === "string" ? raw.lastSuccessAt : null,
    };
  }

  return snapshot;
}

export function hardwareHealthRows(health: BinHardwareHealth | null): HardwareHealthDisplay[] {
  return hardwareHealthComponentKeys.map((key) => {
    const defaults = componentDefaults[key];
    const component = health?.components?.[key];

    return {
      key,
      label: defaults.label,
      status: component?.status ?? "unknown",
      statusLabel: statusLabel(component?.status ?? "unknown"),
      message: component?.message || "No detailed health received.",
      faultCode: component?.faultCode ?? null,
      lastCheckedAt: component?.lastCheckedAt || health?.deviceLastCheckedAt || null,
      lastSuccessAt: component?.lastSuccessAt || null,
      icon: defaults.icon,
    };
  });
}

export function overallHardwareStatus(health: BinHardwareHealth | null): HardwareHealthOverallStatus {
  if (health?.overallStatus) return health.overallStatus;
  return "unknown";
}

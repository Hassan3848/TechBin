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
  const source = normalizeHardwareHealthSource(value);
  if (!source) return null;

  const snapshot = {} as HardwareHealthSnapshot;
  for (const key of hardwareHealthComponentKeys) {
    const defaults = componentDefaults[key];
    const raw = source[key] ?? source[defaults.componentId];
    if (!isRecord(raw) || !isHealthStatus(raw.status)) return null;
    snapshot[key] = normalizeComponent(raw, defaults);
  }

  return snapshot;
}

function normalizeHardwareHealthSource(value: unknown): Record<string, unknown> | null {
  if (Array.isArray(value)) {
    return value.reduce<Record<string, unknown>>((acc, item) => {
      if (!isRecord(item)) return acc;
      const componentId = typeof item.componentId === "string" ? item.componentId : typeof item.component_id === "string" ? item.component_id : null;
      if (componentId) acc[componentId] = item;
      return acc;
    }, {});
  }

  if (!isRecord(value)) return null;

  const components = value.components;
  if (components) return normalizeHardwareHealthSource(components);

  return value;
}

function normalizeComponent(raw: Record<string, unknown>, defaults: { label: string; componentId: string; icon: React.ElementType }): HardwareHealthComponent {
  const componentId = typeof raw.componentId === "string" ? raw.componentId : typeof raw.component_id === "string" ? raw.component_id : defaults.componentId;
  const displayName = typeof raw.displayName === "string"
    ? raw.displayName
    : typeof raw.display_name === "string"
      ? raw.display_name
      : defaults.label;
  const faultCode = typeof raw.faultCode === "string" ? raw.faultCode : typeof raw.fault_code === "string" ? raw.fault_code : null;
  const lastCheckedAt = typeof raw.lastCheckedAt === "string"
    ? raw.lastCheckedAt
    : typeof raw.last_checked_at === "string"
      ? raw.last_checked_at
      : "";
  const lastSuccessAt = typeof raw.lastSuccessAt === "string"
    ? raw.lastSuccessAt
    : typeof raw.last_success_at === "string"
      ? raw.last_success_at
      : null;

  return {
    componentId,
    displayName: displayName.trim() || defaults.label,
    status: isHealthStatus(raw.status) ? raw.status : "unknown",
    faultCode,
    message: typeof raw.message === "string" ? raw.message : "No component message received.",
    consecutiveFailures: typeof raw.consecutiveFailures === "number" ? raw.consecutiveFailures : typeof raw.consecutive_failures === "number" ? raw.consecutive_failures : 0,
    consecutiveSuccesses: typeof raw.consecutiveSuccesses === "number" ? raw.consecutiveSuccesses : typeof raw.consecutive_successes === "number" ? raw.consecutive_successes : 0,
    lastCheckedAt,
    lastSuccessAt,
  };
}

export function hasAnyDetailedHardwareHealth(health: BinHardwareHealth | null): boolean {
  return Boolean(health?.components && hardwareHealthComponentKeys.some((key) => health.components?.[key]));
}

export function missingHardwareHealthComponentLabels(health: BinHardwareHealth | null): string[] {
  if (!health?.components) return hardwareHealthComponentKeys.map((key) => componentDefaults[key].label);
  return hardwareHealthComponentKeys
    .filter((key) => !health.components?.[key])
    .map((key) => componentDefaults[key].label);
}

/*
  Keep this strict variant available for diagnostics and future ingestion-side tests.
  The dashboard parser above intentionally accepts deployed rows that may be keyed
  by componentId or wrapped under a `components` property.
*/
export function parseStrictHardwareHealthSnapshot(value: unknown): HardwareHealthSnapshot | null {
  if (!isRecord(value)) return null;

  const snapshot = {} as HardwareHealthSnapshot;
  for (const key of hardwareHealthComponentKeys) {
    const raw = value[key];
    const defaults = componentDefaults[key];
    if (!isRecord(raw) || !isHealthStatus(raw.status)) return null;
    snapshot[key] = normalizeComponent(raw, defaults);
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

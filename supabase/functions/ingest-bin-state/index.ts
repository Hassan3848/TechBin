import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { adminClient, normalizeOrgId } from "../_shared/admin.ts";

const allowedCategories = new Set(["cardboard", "paper", "plastic_glass", "metal", "trash"]);
const allowedSides = new Set(["recyclable", "non_recyclable"]);
const allowedHealthStatuses = new Set(["healthy", "warning", "critical", "disabled", "not_installed", "unknown"]);
const supportedHealthComponents = {
  frontUltrasonic: "front_ultrasonic",
  leftUltrasonic: "left_ultrasonic",
  rightUltrasonic: "right_ultrasonic",
  camera: "camera",
  network: "network",
  metalDetector: "metal_detector",
  voiceFeedback: "voice_feedback",
  telemetryQueue: "telemetry_queue",
} as const;

type HealthComponentKey = keyof typeof supportedHealthComponents;
type HealthComponent = {
  componentId: string;
  displayName: string;
  status: string;
  faultCode: string | null;
  message: string;
  consecutiveFailures: number;
  consecutiveSuccesses: number;
  lastCheckedAt: string;
  lastSuccessAt: string | null;
};
type HardwareHealth = Record<HealthComponentKey, HealthComponent>;

async function sha256Hex(value: string) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function normalizeText(value: unknown) {
  const text = String(value ?? "").trim();
  return text || null;
}

function hasOwn(value: Record<string, unknown>, key: string) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireIsoTimestamp(value: unknown, path: string) {
  if (typeof value !== "string" || !value.trim() || Number.isNaN(Date.parse(value))) {
    throw new Error(`${path} must be a valid ISO timestamp.`);
  }
  return new Date(value).toISOString();
}

function optionalIsoTimestamp(value: unknown, path: string) {
  if (value === null) return null;
  return requireIsoTimestamp(value, path);
}

function requireNonNegativeInteger(value: unknown, path: string) {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new Error(`${path} must be a non-negative integer.`);
  }
  return value;
}

function validateHardwareHealth(value: unknown): {
  hardwareHealth: HardwareHealth;
  overallStatus: "healthy" | "warning" | "critical" | "unknown";
  deviceLastCheckedAt: string | null;
  deviceLastSuccessAt: string | null;
} {
  if (!isPlainObject(value)) throw new Error("hardwareHealth must be an object.");

  const expectedKeys = Object.keys(supportedHealthComponents) as HealthComponentKey[];
  const suppliedKeys = Object.keys(value);
  const unexpectedKey = suppliedKeys.find((key) => !expectedKeys.includes(key as HealthComponentKey));
  if (unexpectedKey) throw new Error(`hardwareHealth.${unexpectedKey} is not a supported component key.`);

  const missingKey = expectedKeys.find((key) => !hasOwn(value, key));
  if (missingKey) throw new Error(`hardwareHealth.${missingKey} is required.`);

  const normalized = {} as HardwareHealth;
  const checkedTimes: string[] = [];
  const successTimes: string[] = [];
  const activeStatuses: string[] = [];

  for (const key of expectedKeys) {
    const raw = value[key];
    if (!isPlainObject(raw)) throw new Error(`hardwareHealth.${key} must be an object.`);

    const allowedFields = new Set([
      "componentId",
      "displayName",
      "status",
      "faultCode",
      "message",
      "consecutiveFailures",
      "consecutiveSuccesses",
      "lastCheckedAt",
      "lastSuccessAt",
    ]);
    const unexpectedField = Object.keys(raw).find((field) => !allowedFields.has(field));
    if (unexpectedField) throw new Error(`hardwareHealth.${key}.${unexpectedField} is not supported.`);

    for (const field of allowedFields) {
      if (!hasOwn(raw, field)) throw new Error(`hardwareHealth.${key}.${field} is required.`);
    }

    if (raw.componentId !== supportedHealthComponents[key]) {
      throw new Error(`hardwareHealth.${key}.componentId must be ${supportedHealthComponents[key]}.`);
    }
    if (typeof raw.displayName !== "string" || !raw.displayName.trim()) {
      throw new Error(`hardwareHealth.${key}.displayName must be a non-empty string.`);
    }
    if (typeof raw.status !== "string" || !allowedHealthStatuses.has(raw.status)) {
      throw new Error("hardwareHealth component status must be one of: healthy, warning, critical, disabled, not_installed, unknown.");
    }
    if (raw.faultCode !== null && (typeof raw.faultCode !== "string" || !raw.faultCode.trim())) {
      throw new Error(`hardwareHealth.${key}.faultCode must be null or a non-empty string.`);
    }
    if (typeof raw.message !== "string") {
      throw new Error(`hardwareHealth.${key}.message must be a string.`);
    }

    const lastCheckedAt = requireIsoTimestamp(raw.lastCheckedAt, `hardwareHealth.${key}.lastCheckedAt`);
    const lastSuccessAt = optionalIsoTimestamp(raw.lastSuccessAt, `hardwareHealth.${key}.lastSuccessAt`);
    checkedTimes.push(lastCheckedAt);
    if (lastSuccessAt) successTimes.push(lastSuccessAt);
    activeStatuses.push(raw.status);

    normalized[key] = {
      componentId: raw.componentId,
      displayName: raw.displayName.trim(),
      status: raw.status,
      faultCode: raw.faultCode,
      message: raw.message,
      consecutiveFailures: requireNonNegativeInteger(raw.consecutiveFailures, `hardwareHealth.${key}.consecutiveFailures`),
      consecutiveSuccesses: requireNonNegativeInteger(raw.consecutiveSuccesses, `hardwareHealth.${key}.consecutiveSuccesses`),
      lastCheckedAt,
      lastSuccessAt,
    };
  }

  const actionableStatuses = activeStatuses.filter((status) => status !== "disabled" && status !== "not_installed");
  const overallStatus = actionableStatuses.includes("critical")
    ? "critical"
    : actionableStatuses.includes("warning")
      ? "warning"
      : actionableStatuses.length > 0 && actionableStatuses.every((status) => status === "healthy")
        ? "healthy"
        : "unknown";

  return {
    hardwareHealth: normalized,
    overallStatus,
    deviceLastCheckedAt: checkedTimes.sort().at(-1) ?? null,
    deviceLastSuccessAt: successTimes.sort().at(-1) ?? null,
  };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return jsonResponse({ error: "Method not allowed." }, 405);

  try {
    const deviceToken = req.headers.get("x-device-token") || req.headers.get("authorization")?.replace("Bearer ", "");
    if (!deviceToken) return jsonResponse({ error: "Missing device token." }, 401);

    const body = await req.json();
    if (!isPlainObject(body)) return jsonResponse({ error: "Request body must be a JSON object." }, 400);
    const orgId = normalizeOrgId(body.orgId, "techbin");
    const binCode = String(body.binCode ?? "BIN-001").trim().toUpperCase();
    const binId = `${orgId}_${binCode}`;
    const tokenHash = await sha256Hex(deviceToken);
    const client = adminClient();

    const { data: device, error: deviceError } = await client
      .from("pi_devices")
      .select("id,bin_id,active")
      .eq("bin_id", binId)
      .eq("token_hash", tokenHash)
      .eq("active", true)
      .single();

    if (deviceError || !device) return jsonResponse({ error: "Invalid device token." }, 401);

    const now = new Date().toISOString();
    const healthInputSupplied = hasOwn(body, "hardwareHealth");
    const validatedHealth = healthInputSupplied ? validateHardwareHealth(body.hardwareHealth) : null;
    const latestEvent = body.latestEvent ?? body.event ?? null;
    const event = latestEvent && typeof latestEvent === "object" && !Array.isArray(latestEvent)
      ? latestEvent as Record<string, unknown>
      : null;
    const eventId = event ? normalizeText(event.eventId ?? event.event_id) : null;
    const category = event ? normalizeText(event.category) : null;
    const disposedSide = event ? normalizeText(event.disposedSide ?? event.disposed_side) : null;
    const expectedSide = event ? normalizeText(event.expectedSide ?? event.expected_side) : null;

    if (latestEvent && !event) return jsonResponse({ error: "latestEvent must be an object." }, 400);
    if (event && !eventId) return jsonResponse({ error: "latestEvent.eventId is required for disposal events." }, 400);
    if (category && !allowedCategories.has(category)) {
      return jsonResponse({ error: "latestEvent.category must be one of: cardboard, paper, plastic_glass, metal, trash." }, 400);
    }
    if (disposedSide && !allowedSides.has(disposedSide)) {
      return jsonResponse({ error: "latestEvent.disposedSide must be recyclable or non_recyclable." }, 400);
    }
    if (expectedSide && !allowedSides.has(expectedSide)) {
      return jsonResponse({ error: "latestEvent.expectedSide must be recyclable or non_recyclable." }, 400);
    }

    const { data: existingState } = await client
      .from("bin_states")
      .select("status,sensors,statistics,faults,latest_event,last_seen")
      .eq("bin_id", binId)
      .maybeSingle();

    const { error: stateError } = await client.from("bin_states").upsert({
      bin_id: binId,
      org_id: orgId,
      bin_code: binCode,
      status: hasOwn(body, "status") ? body.status : existingState?.status ?? { state: "normal", lastSeen: now },
      sensors: hasOwn(body, "sensors") ? body.sensors : existingState?.sensors ?? {},
      statistics: hasOwn(body, "statistics") ? body.statistics : existingState?.statistics ?? {},
      faults: hasOwn(body, "faults") ? body.faults : existingState?.faults ?? {},
      latest_event: latestEvent ? latestEvent : existingState?.latest_event ?? null,
      last_seen: body.lastSeen ?? now,
      updated_at: now,
    });
    if (stateError) throw stateError;

    if (validatedHealth) {
      const { error: healthError } = await client.from("bin_hardware_health").upsert({
        bin_id: binId,
        org_id: orgId,
        bin_code: binCode,
        hardware_health: validatedHealth.hardwareHealth,
        overall_status: validatedHealth.overallStatus,
        received_at: now,
        device_last_checked_at: validatedHealth.deviceLastCheckedAt,
        device_last_success_at: validatedHealth.deviceLastSuccessAt,
        last_seen: body.lastSeen ?? now,
        updated_at: now,
      });
      if (healthError) throw healthError;
    }

    if (event && eventId) {
      const { error: eventError } = await client.from("bin_events").upsert({
        event_id: eventId,
        bin_id: binId,
        org_id: orgId,
        bin_code: binCode,
        timestamp: event.timestamp ?? now,
        label: event.label ?? null,
        category,
        recyclable: event.recyclable ?? null,
        disposed_side: disposedSide,
        expected_side: expectedSide,
        correct: event.correct ?? null,
        confidence: event.confidence ?? null,
        image_url: event.imageUrl ?? event.image_url ?? null,
        payload: event,
      }, {
        onConflict: "bin_id,event_id",
        ignoreDuplicates: true,
      });
      if (eventError) throw eventError;
    }

    await client.from("pi_devices").update({ last_seen: now }).eq("id", device.id);
    return jsonResponse({ ok: true, binId, healthUpdated: Boolean(validatedHealth), eventRecorded: Boolean(event && eventId) });
  } catch (error) {
    return jsonResponse({ error: error instanceof Error ? error.message : "Ingest failed." }, 400);
  }
});

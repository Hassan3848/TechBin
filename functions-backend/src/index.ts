// functions-backend/src/index.ts
import * as functions from "firebase-functions/v1";
import { initializeApp } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { getFirestore, FieldValue } from "firebase-admin/firestore";

initializeApp();

type Role = "Admin" | "Viewer";

// ✅ Permanent root admin(s)
const FIRST_ADMIN_EMAILS = ["admin@techbin.com"];

// ✅ Provider org (TechBin). Any Admin inside this org becomes superAdmin.
const PROVIDER_ORG_ID = "techbin";

function normalizeEmail(email?: string | null) {
  return String(email || "").trim().toLowerCase();
}


function orgIdFromEmail(email: string): string {
  const domain = (email.split("@")[1] || "").toLowerCase();
  const parts = domain.split(".").filter(Boolean);

  // techbin.com
  if (parts.length >= 2 && parts[0] === "techbin" && parts[1] === "com") return "techbin";

  // techbin.<org>.com (e.g., techbin.evergreen.com -> evergreen)
  if (parts.length >= 3 && parts[0] === "techbin") return parts[1];

  // fallback
  return parts[0] || "unknown";
}

function requireAuth(context: functions.https.CallableContext) {
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "You must be logged in.");
  }
}

function requireAdmin(context: functions.https.CallableContext) {
  requireAuth(context);
  if (context.auth?.token?.admin !== true) {
    throw new functions.https.HttpsError("permission-denied", "Admin only.");
  }
}

function getCallerOrgId(context: functions.https.CallableContext): string {
  const orgId = context.auth?.token?.orgId;
  return typeof orgId === "string" && orgId.trim() ? orgId : "unknown";
}

function isCallerSuperAdmin(context: functions.https.CallableContext): boolean {
  return context.auth?.token?.superAdmin === true;
}

function isProviderAdmin(orgId: string, role: Role) {
  return orgId === PROVIDER_ORG_ID && role === "Admin";
}

type Claims = {
  admin: boolean;
  role: Role;
  orgId: string;
  superAdmin: boolean;
};

async function setClaims(uid: string, claims: Claims) {
  await getAuth().setCustomUserClaims(uid, claims);
}

function readRoleFromClaims(claims: Record<string, unknown> | undefined): Role | null {
  if (!claims) return null;
  const role = claims["role"];
  const adminFlag = claims["admin"];
  if (role === "Admin" || role === "Viewer") return role as Role;
  if (adminFlag === true) return "Admin";
  if (adminFlag === false) return "Viewer";
  return null;
}

function readOrgIdFromClaims(claims: Record<string, unknown> | undefined): string | null {
  if (!claims) return null;
  const orgId = claims["orgId"];
  if (typeof orgId === "string" && orgId.trim()) return orgId;
  return null;
}

/**
 * ✅ AUTO ASSIGN CLAIMS + USER PROFILE ON AUTH USER CREATION
 *
 * IMPORTANT:
 * - If claims already exist (because adminCreateUser already set them),
 *   DO NOT overwrite (otherwise Admin-created "Admin" could become Viewer).
 */
export const onAuthUserCreate = functions.auth.user().onCreate(async (user) => {
  const email = normalizeEmail(user.email);

  // If no email, still create a minimal doc
  if (!email) {
    await getFirestore().collection("users").doc(user.uid).set(
      {
        email: "",
        orgId: "unknown",
        role: "Viewer",
        disabled: false,
        createdAt: FieldValue.serverTimestamp(),
        createdBy: "system-onCreate-noEmail",
      },
      { merge: true }
    );
    return;
  }

  // ✅ If claims already exist, keep them
  const userRecord = await getAuth().getUser(user.uid);
  const existingClaims = userRecord.customClaims as Record<string, unknown> | undefined;

  const existingRole = readRoleFromClaims(existingClaims);
  const existingOrgId = readOrgIdFromClaims(existingClaims);

  if (existingRole && existingOrgId) {
    await getFirestore().collection("users").doc(user.uid).set(
      {
        email,
        orgId: existingOrgId,
        role: existingRole,
        disabled: false,
        createdAt: FieldValue.serverTimestamp(),
        createdBy: "system-onCreate-existingClaims",
      },
      { merge: true }
    );
    return;
  }

  // ✅ Otherwise assign default based on FIRST_ADMIN_EMAILS
  const orgId = orgIdFromEmail(email);
  const isRootAdmin = FIRST_ADMIN_EMAILS.includes(email);
  const role: Role = isRootAdmin ? "Admin" : "Viewer";

  const adminFlag = role === "Admin";
  const superAdmin = isProviderAdmin(orgId, role); // any Admin in techbin org

  await setClaims(user.uid, { admin: adminFlag, role, orgId, superAdmin });

  await getFirestore().collection("users").doc(user.uid).set(
    {
      email,
      orgId,
      role,
      disabled: false,
      createdAt: FieldValue.serverTimestamp(),
      createdBy: "system-onCreate",
    },
    { merge: true }
  );

  return;
});

/**
 * ✅ BOOTSTRAP ROOT ADMIN (FOR EXISTING ACCOUNTS)
 */
export const bootstrapMakeAdmin = functions.https.onCall(async (_data: unknown, context) => {
  requireAuth(context);

  const email = normalizeEmail(context.auth?.token?.email as string | undefined);
  if (!FIRST_ADMIN_EMAILS.includes(email)) {
    throw new functions.https.HttpsError("permission-denied", "Not allowed");
  }

  const uid = context.auth!.uid;

  const orgId = orgIdFromEmail(email);
  const role: Role = "Admin";
  const superAdmin = isProviderAdmin(orgId, role);

  await setClaims(uid, { admin: true, role, orgId, superAdmin });

  await getFirestore().collection("users").doc(uid).set(
    {
      email,
      orgId,
      role: "Admin",
      disabled: false,
      createdAt: FieldValue.serverTimestamp(),
      createdBy: "bootstrap",
      updatedAt: FieldValue.serverTimestamp(),
      updatedBy: "bootstrap",
    },
    { merge: true }
  );

  return { ok: true };
});

type CreateUserInput = {
  email: string;
  password: string;
  role?: Role;
  displayName?: string;
  // Only superAdmin can set orgId explicitly (optional)
  orgId?: string;
};

/**
 * ✅ ADMIN CREATES USER (Multi-tenant)
 * - superAdmin can create users for any org (orgId optional)
 * - org admin can create users ONLY in their org
 */
export const adminCreateUser = functions.https.onCall(async (data: CreateUserInput, context) => {
  requireAdmin(context);

  const email = normalizeEmail(data?.email);
  const password = String(data?.password || "");
  const role: Role = data?.role === "Admin" ? "Admin" : "Viewer";
  const displayName = String(data?.displayName || "").trim();

  if (!email) {
    throw new functions.https.HttpsError("invalid-argument", "Email is required.");
  }
  if (password.length < 6) {
    throw new functions.https.HttpsError("invalid-argument", "Password must be at least 6 characters.");
  }

  const callerOrgId = getCallerOrgId(context);
  const callerSuper = isCallerSuperAdmin(context);

  const requestedOrgId = String(data?.orgId || "").trim().toLowerCase();
  const inferredOrgId = orgIdFromEmail(email);
  const targetOrgId = callerSuper ? (requestedOrgId || inferredOrgId) : callerOrgId;

  if (!callerSuper && targetOrgId !== callerOrgId) {
    throw new functions.https.HttpsError("permission-denied", "You can only create users in your own organization.");
  }

  try {
    const userRecord = await getAuth().createUser({
      email,
      password,
      displayName: displayName || undefined,
    });

    const adminFlag = role === "Admin";
    const superAdmin = isProviderAdmin(targetOrgId, role);

    await setClaims(userRecord.uid, { admin: adminFlag, role, orgId: targetOrgId, superAdmin });

    await getFirestore().collection("users").doc(userRecord.uid).set(
      {
        email,
        displayName: displayName || null,
        role,
        orgId: targetOrgId,
        disabled: false,
        createdAt: FieldValue.serverTimestamp(),
        createdBy: context.auth!.uid,
      },
      { merge: true }
    );

    return { uid: userRecord.uid, email, role, orgId: targetOrgId };
  } catch (err: unknown) {
    const e = err as { code?: unknown; message?: unknown };
    const code = typeof e.code === "string" ? e.code : "";
    const message = typeof e.message === "string" ? e.message : "Failed to create user.";

    if (code.includes("email-already-exists")) {
      throw new functions.https.HttpsError("already-exists", "Email already exists.");
    }

    console.error("adminCreateUser error:", err);
    throw new functions.https.HttpsError("internal", message);
  }
});

type DeleteUserInput = {
  uid?: string;
  email?: string;
};

/**
 * ✅ ADMIN DELETES USER (Auth + Firestore) with tenant enforcement
 * - superAdmin can delete anyone (except root admin)
 * - org admin can delete only users in their org
 */
export const adminDeleteUser = functions.https.onCall(async (data: DeleteUserInput, context) => {
  requireAdmin(context);

  const inputUid = String(data?.uid || "").trim();
  const inputEmail = normalizeEmail(data?.email);

  if (!inputUid && !inputEmail) {
    throw new functions.https.HttpsError("invalid-argument", "uid or email is required.");
  }

  let uid = inputUid;
  let email = inputEmail;

  if (!uid && email) {
    const userByEmail = await getAuth().getUserByEmail(email);
    uid = userByEmail.uid;
    email = normalizeEmail(userByEmail.email);
  }

  // Prevent deleting yourself
  if (uid === context.auth!.uid) {
    throw new functions.https.HttpsError("failed-precondition", "You cannot delete your own account.");
  }

  // Prevent deleting root admin
  if (email && FIRST_ADMIN_EMAILS.includes(email)) {
    throw new functions.https.HttpsError("failed-precondition", "You cannot delete the root admin.");
  }

  const callerSuper = isCallerSuperAdmin(context);
  const callerOrgId = getCallerOrgId(context);

  // Tenant check via Firestore (source of truth for target org)
  const docRef = getFirestore().collection("users").doc(uid);
  const snap = await docRef.get();
  const targetOrgId = snap.exists ? String((snap.data() as any)?.orgId || "unknown") : "unknown";

  if (!callerSuper && targetOrgId !== callerOrgId) {
    throw new functions.https.HttpsError("permission-denied", "You can only delete users in your own organization.");
  }

  // Delete Auth user (ignore if already deleted)
  try {
    await getAuth().deleteUser(uid);
  } catch (err: unknown) {
    const e = err as { code?: unknown };
    const code = typeof e.code === "string" ? e.code : "";
    if (!code.includes("auth/user-not-found")) {
      console.error("deleteUser(auth) error:", err);
      throw new functions.https.HttpsError("internal", "Failed to delete user from Auth.");
    }
  }

  // Delete Firestore doc
  try {
    await docRef.delete();
  } catch (err) {
    console.error("deleteUser(firestore) error:", err);
    throw new functions.https.HttpsError("internal", "Deleted from Auth, but failed deleting Firestore profile.");
  }

  return { ok: true, uid };
});

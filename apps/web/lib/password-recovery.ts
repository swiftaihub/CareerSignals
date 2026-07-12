import { createHmac, timingSafeEqual } from "node:crypto";

import { safeRedirectPath } from "./navigation";

export const RECOVERY_AUTH_COOKIE_NAME = "careersignals-recovery-auth";
export const RECOVERY_INTENT_COOKIE_NAME = "careersignals-recovery-intent";
export const RECOVERY_AUTH_COOKIE_MAX_AGE = 60 * 60;
export const RECOVERY_INTENT_COOKIE_MAX_AGE = 15 * 60;

// Explicit aliases keep the unit visible at call sites that set cookie options.
export const RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS = RECOVERY_AUTH_COOKIE_MAX_AGE;
export const RECOVERY_INTENT_COOKIE_MAX_AGE_SECONDS = RECOVERY_INTENT_COOKIE_MAX_AGE;
export const RECOVERY_AUTH_MAX_AGE_SECONDS = RECOVERY_AUTH_COOKIE_MAX_AGE;
export const RECOVERY_INTENT_MAX_AGE_SECONDS = RECOVERY_INTENT_COOKIE_MAX_AGE;

const TRUSTED_REDIRECT_ORIGIN = "https://careersignals.invalid";
const RECOVERY_REDIRECT_PATH = "/reset-password";
const RECOVERY_ROUTES = new Set([
  "/forgot-password",
  RECOVERY_REDIRECT_PATH,
  "/auth/callback"
]);
const RECOVERY_CODE_VERIFIER_COOKIE_NAME = `${RECOVERY_AUTH_COOKIE_NAME}-code-verifier`;
const MINIMUM_RECOVERY_SECRET_BYTES = 32;
const INSECURE_EXAMPLE_SECRETS = new Set([
  "replace-with-32-plus-byte-random-secret",
  "change-me-to-a-random-32-byte-secret"
]);
const MAX_INTENT_TOKEN_LENGTH = 4096;
const MAX_IDENTITY_VALUE_LENGTH = 256;

export interface RecoveryIntentIdentity {
  userId: string;
  sessionId: string;
}

interface RecoveryIntentPayload extends RecoveryIntentIdentity {
  version: 1;
  expiresAt: number;
}

export type RecoveryAuthCookieKind = "session" | "code-verifier";

/**
 * Returns the configured application origin after enforcing the production
 * transport policy. Request Host headers must never be used as a fallback.
 */
export function trustedSiteOrigin(
  configured: string | null | undefined,
  nodeEnv: string | null | undefined
) {
  const candidate = configured?.trim();
  if (
    !candidate
    || !/^https?:\/\//i.test(candidate)
    || /[\\\u0000-\u001f\u007f]/.test(candidate)
  ) {
    throw new Error("NEXT_PUBLIC_SITE_URL must be an absolute HTTP(S) URL.");
  }

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error("NEXT_PUBLIC_SITE_URL must be an absolute HTTP(S) URL.");
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_SITE_URL must use HTTP or HTTPS.");
  }
  if (parsed.username || parsed.password) {
    throw new Error("NEXT_PUBLIC_SITE_URL must not contain credentials.");
  }
  if (nodeEnv === "production" && parsed.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_SITE_URL must use HTTPS in production.");
  }

  return parsed.origin;
}

/**
 * Sanitizes a recovery destination and limits it to the reset page. Query and
 * fragment data are retained only when the normalized pathname is exact.
 */
export function recoveryRedirectPath(value: unknown) {
  const safePath = safeRedirectPath(value, RECOVERY_REDIRECT_PATH);

  try {
    const parsed = new URL(safePath, TRUSTED_REDIRECT_ORIGIN);
    if (
      parsed.origin !== TRUSTED_REDIRECT_ORIGIN ||
      parsed.pathname !== RECOVERY_REDIRECT_PATH
    ) {
      return RECOVERY_REDIRECT_PATH;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return RECOVERY_REDIRECT_PATH;
  }
}

export function isRecoveryRouteAllowed(pathname: unknown) {
  return typeof pathname === "string" && RECOVERY_ROUTES.has(pathname);
}

export function isRecoveryIntentSecretConfigured(value: unknown): value is string {
  if (typeof value !== "string") return false;
  return Buffer.byteLength(value, "utf8") >= MINIMUM_RECOVERY_SECRET_BYTES
    && !INSECURE_EXAMPLE_SECRETS.has(value.trim().toLowerCase());
}

function isBaseOrChunk(name: string, baseName: string) {
  if (name === baseName) return true;
  if (!name.startsWith(`${baseName}.`)) return false;
  const chunk = name.slice(baseName.length + 1);
  return /^\d+$/.test(chunk);
}

/** Distinguishes recovery session cookies from PKCE verifier cookies. */
export function recoveryAuthCookieKind(name: unknown): RecoveryAuthCookieKind | null {
  if (typeof name !== "string") return null;
  if (isBaseOrChunk(name, RECOVERY_CODE_VERIFIER_COOKIE_NAME)) return "code-verifier";
  if (isBaseOrChunk(name, RECOVERY_AUTH_COOKIE_NAME)) return "session";
  return null;
}

export function isRecoveryAuthCookieName(name: unknown) {
  return recoveryAuthCookieKind(name) !== null;
}

export function isRecoveryAuthSessionCookieName(name: unknown) {
  return recoveryAuthCookieKind(name) === "session";
}

export function isRecoveryCodeVerifierCookieName(name: unknown) {
  return recoveryAuthCookieKind(name) === "code-verifier";
}

/**
 * Reads an unverified JWT claim. Callers must validate the JWT with Supabase
 * before using the returned session ID for an authorization decision.
 */
export function extractSessionId(jwt: unknown): string | null {
  if (typeof jwt !== "string") return null;
  const parts = jwt.split(".");
  if (parts.length !== 3 || !parts[1] || !/^[A-Za-z0-9_-]+$/.test(parts[1])) {
    return null;
  }

  try {
    const decoded = Buffer.from(parts[1], "base64url").toString("utf8");
    const payload: unknown = JSON.parse(decoded);
    if (!isRecord(payload)) return null;
    const sessionId = payload.session_id;
    return typeof sessionId === "string" && sessionId.trim() ? sessionId : null;
  } catch {
    return null;
  }
}

export function createRecoveryIntent(
  identity: RecoveryIntentIdentity,
  secret: string,
  nowSeconds = currentEpochSeconds()
) {
  assertRecoverySecret(secret);
  assertIdentity(identity);
  const now = normalizedEpochSeconds(nowSeconds);
  const payload: RecoveryIntentPayload = {
    version: 1,
    userId: identity.userId,
    sessionId: identity.sessionId,
    expiresAt: now + RECOVERY_INTENT_COOKIE_MAX_AGE
  };
  const encodedPayload = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  return `${encodedPayload}.${intentSignature(encodedPayload, secret).toString("base64url")}`;
}

export function verifyRecoveryIntent(
  token: unknown,
  identity: RecoveryIntentIdentity,
  secret: string,
  nowSeconds = currentEpochSeconds()
) {
  assertRecoverySecret(secret);
  if (!isValidIdentity(identity)) return false;
  const now = normalizedEpochSeconds(nowSeconds);
  if (typeof token !== "string" || !token || token.length > MAX_INTENT_TOKEN_LENGTH) {
    return false;
  }

  const parts = token.split(".");
  if (parts.length !== 2 || !parts[0] || !parts[1]) return false;
  const [encodedPayload, encodedSignature] = parts;
  if (!/^[A-Za-z0-9_-]+$/.test(encodedPayload)) return false;

  const expectedSignature = intentSignature(encodedPayload, secret);
  const suppliedSignature = decodeSignature(encodedSignature);
  const comparableSignature = suppliedSignature?.length === expectedSignature.length
    ? suppliedSignature
    : Buffer.alloc(expectedSignature.length);
  const signatureMatches = timingSafeEqual(expectedSignature, comparableSignature)
    && suppliedSignature?.length === expectedSignature.length;
  if (!signatureMatches) return false;

  try {
    const decoded = Buffer.from(encodedPayload, "base64url").toString("utf8");
    const payload: unknown = JSON.parse(decoded);
    if (!isRecoveryIntentPayload(payload)) return false;
    return payload.userId === identity.userId
      && payload.sessionId === identity.sessionId
      && payload.expiresAt > now;
  } catch {
    return false;
  }
}

function currentEpochSeconds() {
  return Math.floor(Date.now() / 1000);
}

function normalizedEpochSeconds(value: number) {
  if (!Number.isFinite(value) || value < 0) {
    throw new Error("Recovery intent time must be a non-negative number.");
  }
  return Math.floor(value);
}

function assertRecoverySecret(secret: string) {
  if (!isRecoveryIntentSecretConfigured(secret)) {
    throw new Error("Recovery intent secret must contain at least 32 bytes.");
  }
}

function isValidIdentity(identity: RecoveryIntentIdentity) {
  return Boolean(
    identity
    && typeof identity.userId === "string"
    && identity.userId.length > 0
    && identity.userId.length <= MAX_IDENTITY_VALUE_LENGTH
    && typeof identity.sessionId === "string"
    && identity.sessionId.length > 0
    && identity.sessionId.length <= MAX_IDENTITY_VALUE_LENGTH
  );
}

function assertIdentity(identity: RecoveryIntentIdentity) {
  if (!isValidIdentity(identity)) {
    throw new Error("Recovery intent identity is invalid.");
  }
}

function intentSignature(encodedPayload: string, secret: string) {
  return createHmac("sha256", secret).update(encodedPayload, "utf8").digest();
}

function decodeSignature(value: string) {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) return null;
  try {
    const decoded = Buffer.from(value, "base64url");
    return decoded.toString("base64url") === value ? decoded : null;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRecoveryIntentPayload(value: unknown): value is RecoveryIntentPayload {
  if (!isRecord(value)) return false;
  return value.version === 1
    && typeof value.userId === "string"
    && typeof value.sessionId === "string"
    && typeof value.expiresAt === "number"
    && Number.isSafeInteger(value.expiresAt)
    && value.expiresAt >= 0;
}

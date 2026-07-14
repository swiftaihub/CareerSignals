import { sanitizeInternalRedirect, stripBasePath } from "./app-path";

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
 * Sanitizes a recovery destination and limits it to the reset page. Query and
 * fragment data are retained only when the normalized pathname is exact.
 */
export function recoveryRedirectPath(value: unknown) {
  const safePath = sanitizeInternalRedirect(value, RECOVERY_REDIRECT_PATH);

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
  return typeof pathname === "string" && RECOVERY_ROUTES.has(stripBasePath(pathname));
}

export function isRecoveryIntentSecretConfigured(value: unknown): value is string {
  if (typeof value !== "string") return false;
  return new TextEncoder().encode(value).byteLength >= MINIMUM_RECOVERY_SECRET_BYTES
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
    const decoded = decodeBase64UrlText(parts[1]);
    if (decoded === null) return null;
    const payload: unknown = JSON.parse(decoded);
    if (!isRecord(payload)) return null;
    const sessionId = payload.session_id;
    return typeof sessionId === "string" && sessionId.trim() ? sessionId : null;
  } catch {
    return null;
  }
}

export async function createRecoveryIntent(
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
  const encodedPayload = encodeBase64UrlText(JSON.stringify(payload));
  return `${encodedPayload}.${await intentSignature(encodedPayload, secret)}`;
}

export async function verifyRecoveryIntent(
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

  const suppliedSignature = decodeSignature(encodedSignature);
  if (!suppliedSignature) return false;
  const signatureMatches = await verifyIntentSignature(
    encodedPayload,
    suppliedSignature,
    secret
  );
  if (!signatureMatches) return false;

  try {
    const decoded = decodeBase64UrlText(encodedPayload);
    if (decoded === null) return false;
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

async function intentSignature(encodedPayload: string, secret: string) {
  const key = await recoveryHmacKey(secret, ["sign"]);
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(encodedPayload)
  );
  return encodeBase64UrlBytes(new Uint8Array(signature));
}

async function verifyIntentSignature(
  encodedPayload: string,
  signature: Uint8Array,
  secret: string
) {
  const key = await recoveryHmacKey(secret, ["verify"]);
  const signatureBytes = new Uint8Array(signature.byteLength);
  signatureBytes.set(signature);
  return crypto.subtle.verify(
    "HMAC",
    key,
    signatureBytes,
    new TextEncoder().encode(encodedPayload)
  );
}

function recoveryHmacKey(secret: string, usages: KeyUsage[]) {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    usages
  );
}

function decodeSignature(value: string) {
  return decodeBase64UrlBytes(value);
}

function encodeBase64UrlText(value: string) {
  return encodeBase64UrlBytes(new TextEncoder().encode(value));
}

function decodeBase64UrlText(value: string) {
  const bytes = decodeBase64UrlBytes(value);
  if (!bytes) return null;
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}

function encodeBase64UrlBytes(value: Uint8Array) {
  let binary = "";
  value.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function decodeBase64UrlBytes(value: string) {
  if (!/^[A-Za-z0-9_-]+$/.test(value)) return null;
  try {
    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const padded = `${base64}${"=".repeat((4 - (base64.length % 4)) % 4)}`;
    const binary = atob(padded);
    const decoded = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return encodeBase64UrlBytes(decoded) === value ? decoded : null;
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

import { describe, expect, it } from "vitest";

import {
  RECOVERY_AUTH_COOKIE_MAX_AGE,
  RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS,
  RECOVERY_AUTH_COOKIE_NAME,
  RECOVERY_AUTH_MAX_AGE_SECONDS,
  RECOVERY_INTENT_COOKIE_MAX_AGE,
  RECOVERY_INTENT_COOKIE_MAX_AGE_SECONDS,
  RECOVERY_INTENT_COOKIE_NAME,
  RECOVERY_INTENT_MAX_AGE_SECONDS,
  createRecoveryIntent,
  extractSessionId,
  isRecoveryAuthCookieName,
  isRecoveryAuthSessionCookieName,
  isRecoveryCodeVerifierCookieName,
  isRecoveryIntentSecretConfigured,
  isRecoveryRouteAllowed,
  recoveryAuthCookieKind,
  recoveryRedirectPath,
  verifyRecoveryIntent
} from "./password-recovery";

const SECRET = "recovery-test-secret-with-at-least-32-bytes";
const IDENTITY = { userId: "user-123", sessionId: "session-456" };

function jwtWithPayload(payload: unknown) {
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
  return `${encode({ alg: "none" })}.${encode(payload)}.signature`;
}

describe("recovery configuration", () => {
  it("uses isolated cookie names and bounded lifetimes", () => {
    expect(RECOVERY_AUTH_COOKIE_NAME).toBe("careersignals-recovery-auth");
    expect(RECOVERY_INTENT_COOKIE_NAME).toBe("careersignals-recovery-intent");
    expect(RECOVERY_AUTH_COOKIE_MAX_AGE).toBe(3600);
    expect(RECOVERY_INTENT_COOKIE_MAX_AGE).toBe(900);
    expect(RECOVERY_AUTH_COOKIE_MAX_AGE_SECONDS).toBe(3600);
    expect(RECOVERY_INTENT_COOKIE_MAX_AGE_SECONDS).toBe(900);
    expect(RECOVERY_AUTH_MAX_AGE_SECONDS).toBe(3600);
    expect(RECOVERY_INTENT_MAX_AGE_SECONDS).toBe(900);
  });

  it("rejects copied example secrets while accepting a generated-length secret", () => {
    expect(isRecoveryIntentSecretConfigured("replace-with-32-plus-byte-random-secret"))
      .toBe(false);
    expect(isRecoveryIntentSecretConfigured(SECRET)).toBe(true);
  });

});

describe("recovery navigation policy", () => {
  it("preserves query and fragment data only for the exact reset pathname", () => {
    expect(recoveryRedirectPath("/reset-password?from=email#form"))
      .toBe("/reset-password?from=email#form");
    expect(recoveryRedirectPath("/reset-password/")).toBe("/reset-password");
    expect(recoveryRedirectPath("/dashboard?from=email#form")).toBe("/reset-password");
  });

  it("falls back safely for external and malformed destinations", () => {
    expect(recoveryRedirectPath("https://evil.example/reset-password")).toBe("/reset-password");
    expect(recoveryRedirectPath("//evil.example/reset-password")).toBe("/reset-password");
    expect(recoveryRedirectPath("/\\\\evil.example/reset-password")).toBe("/reset-password");
    expect(recoveryRedirectPath(undefined)).toBe("/reset-password");
  });

  it("allows only the exact recovery routes", () => {
    expect(isRecoveryRouteAllowed("/forgot-password")).toBe(true);
    expect(isRecoveryRouteAllowed("/reset-password")).toBe(true);
    expect(isRecoveryRouteAllowed("/auth/callback")).toBe(true);
    expect(isRecoveryRouteAllowed("/reset-password/")).toBe(false);
    expect(isRecoveryRouteAllowed("/reset-password?step=1")).toBe(false);
    expect(isRecoveryRouteAllowed("/dashboard")).toBe(false);
  });
});

describe("recovery cookie classification", () => {
  it("distinguishes session base/chunks from PKCE verifier base/chunks", () => {
    expect(recoveryAuthCookieKind(RECOVERY_AUTH_COOKIE_NAME)).toBe("session");
    expect(recoveryAuthCookieKind(`${RECOVERY_AUTH_COOKIE_NAME}.0`)).toBe("session");
    expect(recoveryAuthCookieKind(`${RECOVERY_AUTH_COOKIE_NAME}.12`)).toBe("session");
    expect(recoveryAuthCookieKind(`${RECOVERY_AUTH_COOKIE_NAME}-code-verifier`))
      .toBe("code-verifier");
    expect(recoveryAuthCookieKind(`${RECOVERY_AUTH_COOKIE_NAME}-code-verifier.1`))
      .toBe("code-verifier");
  });

  it("rejects lookalike and malformed cookie names", () => {
    expect(recoveryAuthCookieKind(`${RECOVERY_AUTH_COOKIE_NAME}.chunk`)).toBeNull();
    expect(recoveryAuthCookieKind(`${RECOVERY_AUTH_COOKIE_NAME}-code-verifier.chunk`)).toBeNull();
    expect(recoveryAuthCookieKind(`${RECOVERY_AUTH_COOKIE_NAME}-other`)).toBeNull();
    expect(isRecoveryAuthCookieName("unrelated-cookie")).toBe(false);
    expect(isRecoveryAuthSessionCookieName(`${RECOVERY_AUTH_COOKIE_NAME}.2`)).toBe(true);
    expect(isRecoveryCodeVerifierCookieName(`${RECOVERY_AUTH_COOKIE_NAME}-code-verifier.2`))
      .toBe(true);
  });
});

describe("JWT session claim extraction", () => {
  it("extracts session_id without treating the JWT as verified", () => {
    expect(extractSessionId(jwtWithPayload({ sub: "user-123", session_id: "session-456" })))
      .toBe("session-456");
  });

  it("rejects malformed JWTs and missing session claims", () => {
    expect(extractSessionId("not-a-jwt")).toBeNull();
    expect(extractSessionId("header.***.signature")).toBeNull();
    expect(extractSessionId(jwtWithPayload({ sub: "user-123" }))).toBeNull();
    expect(extractSessionId(jwtWithPayload({ session_id: "" }))).toBeNull();
    expect(extractSessionId(null)).toBeNull();
  });
});

describe("signed recovery intent", () => {
  it("rejects a missing recovery intent marker", async () => {
    await expect(verifyRecoveryIntent(undefined, IDENTITY, SECRET, 1_000)).resolves.toBe(false);
  });

  it("accepts a valid marker bound to the expected user and session", async () => {
    const marker = await createRecoveryIntent(IDENTITY, SECRET, 1_000);
    await expect(verifyRecoveryIntent(marker, IDENTITY, SECRET, 1_000)).resolves.toBe(true);
    await expect(verifyRecoveryIntent(marker, IDENTITY, SECRET, 1_899)).resolves.toBe(true);
  });

  it("rejects expired markers", async () => {
    const marker = await createRecoveryIntent(IDENTITY, SECRET, 1_000);
    await expect(verifyRecoveryIntent(marker, IDENTITY, SECRET, 1_900)).resolves.toBe(false);
    await expect(verifyRecoveryIntent(marker, IDENTITY, SECRET, 2_000)).resolves.toBe(false);
  });

  it("rejects markers for a different user or session", async () => {
    const marker = await createRecoveryIntent(IDENTITY, SECRET, 1_000);
    await expect(verifyRecoveryIntent(marker, { ...IDENTITY, userId: "other-user" }, SECRET, 1_000))
      .resolves.toBe(false);
    await expect(verifyRecoveryIntent(marker, { ...IDENTITY, sessionId: "other-session" }, SECRET, 1_000))
      .resolves.toBe(false);
  });

  it("rejects payload and signature tampering", async () => {
    const marker = await createRecoveryIntent(IDENTITY, SECRET, 1_000);
    const [payload, signature] = marker.split(".");
    const tamperedPayload = `${payload.slice(0, -1)}${payload.endsWith("A") ? "B" : "A"}`;
    const tamperedSignature = `${signature.slice(0, -1)}${signature.endsWith("A") ? "B" : "A"}`;
    await expect(verifyRecoveryIntent(`${tamperedPayload}.${signature}`, IDENTITY, SECRET, 1_000))
      .resolves.toBe(false);
    await expect(verifyRecoveryIntent(`${payload}.${tamperedSignature}`, IDENTITY, SECRET, 1_000))
      .resolves.toBe(false);
    await expect(verifyRecoveryIntent("malformed", IDENTITY, SECRET, 1_000)).resolves.toBe(false);
  });

  it("requires a secret containing at least 32 bytes", async () => {
    await expect(createRecoveryIntent(IDENTITY, "x".repeat(31), 1_000))
      .rejects.toThrow(/32 bytes/i);
    const marker = await createRecoveryIntent(IDENTITY, SECRET, 1_000);
    await expect(verifyRecoveryIntent(marker, IDENTITY, "x".repeat(31), 1_000))
      .rejects.toThrow(/32 bytes/i);
  });
});

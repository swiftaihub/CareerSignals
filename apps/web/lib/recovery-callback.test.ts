import { describe, expect, it, vi } from "vitest";

import { exchangeRecoveryCode } from "./recovery-callback";

const accessToken = [
  Buffer.from(JSON.stringify({ alg: "none" })).toString("base64url"),
  Buffer.from(JSON.stringify({ session_id: "session-123" })).toString("base64url"),
  "signature"
].join(".");

function validData() {
  return {
    redirectType: "recovery",
    session: { access_token: accessToken },
    user: { id: "user-123" }
  };
}

describe("exchangeRecoveryCode", () => {
  it("accepts a valid password-recovery code exchange", async () => {
    const exchange = vi.fn().mockResolvedValue({ data: validData(), error: null });
    const result = await exchangeRecoveryCode("authorization-code", exchange);

    expect(result).toEqual({
      ok: true,
      value: {
        identity: { userId: "user-123", sessionId: "session-123" },
        session: { access_token: accessToken }
      }
    });
    expect(exchange).toHaveBeenCalledWith("authorization-code");
  });

  it("rejects a missing code without calling Supabase", async () => {
    const exchange = vi.fn();
    await expect(exchangeRecoveryCode(null, exchange)).resolves.toEqual({
      ok: false,
      reason: "missing"
    });
    expect(exchange).not.toHaveBeenCalled();
  });

  it.each(["bad_code_verifier", "flow_state_expired", "otp_expired"])(
    "rejects a failed or expired exchange (%s)",
    async (code) => {
      const exchange = vi.fn().mockResolvedValue({
        data: { session: null, user: null },
        error: { code }
      });
      await expect(exchangeRecoveryCode("authorization-code", exchange)).resolves.toEqual({
        ok: false,
        reason: "invalid"
      });
    }
  );

  it("rejects a valid non-recovery PKCE code", async () => {
    const exchange = vi.fn().mockResolvedValue({
      data: { ...validData(), redirectType: null },
      error: null
    });
    await expect(exchangeRecoveryCode("authorization-code", exchange)).resolves.toEqual({
      ok: false,
      reason: "not-recovery"
    });
  });
});

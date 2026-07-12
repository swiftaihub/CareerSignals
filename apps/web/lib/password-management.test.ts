import { describe, expect, it, vi } from "vitest";

import {
  authenticatedUpdateErrorMessage,
  requestPasswordReset,
  updateAuthenticatedPassword,
  updateRecoveryPassword
} from "./password-management";
import {
  PASSWORD_CHANGE_SUCCESS_MESSAGE,
  RESET_REQUEST_SUCCESS_MESSAGE
} from "./password-policy";

describe("requestPasswordReset", () => {
  it("returns the same response for known and unknown account outcomes", async () => {
    const known = await requestPasswordReset({
      email: "known@example.com",
      redirectTo: "https://app.example/auth/callback?next=/reset-password",
      send: vi.fn().mockResolvedValue({ error: null })
    });
    const unknown = await requestPasswordReset({
      email: "unknown@example.com",
      redirectTo: "https://app.example/auth/callback?next=/reset-password",
      send: vi.fn().mockResolvedValue({ error: { code: "user_not_found" } })
    });

    expect(known).toEqual({ success: RESET_REQUEST_SUCCESS_MESSAGE });
    expect(unknown).toEqual(known);
  });

  it("maps rate limits and network failures without exposing internals", async () => {
    const limited = await requestPasswordReset({
      email: "person@example.com",
      redirectTo: "https://app.example/auth/callback?next=/reset-password",
      send: vi.fn().mockResolvedValue({
        error: { code: "over_email_send_rate_limit", message: "internal detail", status: 429 }
      })
    });
    const unavailable = await requestPasswordReset({
      email: "person@example.com",
      redirectTo: "https://app.example/auth/callback?next=/reset-password",
      send: vi.fn().mockRejectedValue(new Error("socket secret"))
    });
    const returnedNetworkError = await requestPasswordReset({
      email: "person@example.com",
      redirectTo: "https://app.example/auth/callback?next=/reset-password",
      send: vi.fn().mockResolvedValue({
        error: {
          name: "AuthRetryableFetchError",
          message: "fetch failed with socket secret",
          status: 0
        }
      })
    });

    expect(limited).toEqual({ success: RESET_REQUEST_SUCCESS_MESSAGE });
    expect(unavailable.error).toContain("temporarily unavailable");
    expect(returnedNetworkError.error).toContain("temporarily unavailable");
    expect(JSON.stringify([limited, unavailable, returnedNetworkError]))
      .not.toContain("internal detail");
    expect(JSON.stringify([limited, unavailable, returnedNetworkError]))
      .not.toContain("socket secret");
  });
});

describe("password updates", () => {
  it("updates a recovery password and globally signs out", async () => {
    const update = vi.fn().mockResolvedValue({ error: null });
    const signOutGlobally = vi.fn().mockResolvedValue(undefined);
    const clearLocalState = vi.fn().mockResolvedValue(undefined);

    await expect(updateRecoveryPassword("new-password", {
      update,
      signOutGlobally,
      clearLocalState
    }))
      .resolves.toEqual({ success: "updated" });
    expect(update).toHaveBeenCalledWith({ password: "new-password" });
    expect(signOutGlobally).toHaveBeenCalledOnce();
    expect(clearLocalState).toHaveBeenCalledOnce();
  });

  it("requires the exact current-password field for an authenticated change", async () => {
    const update = vi.fn().mockResolvedValue({ error: null });
    const signOutGlobally = vi.fn().mockResolvedValue(undefined);

    await expect(updateAuthenticatedPassword("old-password", "new-password", {
      update,
      signOutGlobally
    })).resolves.toEqual({ success: PASSWORD_CHANGE_SUCCESS_MESSAGE });
    expect(update).toHaveBeenCalledWith({
      password: "new-password",
      current_password: "old-password"
    });
    expect(signOutGlobally).toHaveBeenCalledOnce();
  });

  it("maps an invalid current password to safe copy", () => {
    expect(authenticatedUpdateErrorMessage({
      code: "current_password_mismatch",
      message: "database detail"
    })).toBe("Current password is incorrect.");
  });

  it("does not call Supabase for a demo password change", async () => {
    const update = vi.fn();
    const signOutGlobally = vi.fn();

    const result = await updateAuthenticatedPassword("old-password", "new-password", {
      update,
      signOutGlobally,
      isDemo: true
    });

    expect(result.error).toBe("Password changes are unavailable for the demo account.");
    expect(update).not.toHaveBeenCalled();
    expect(signOutGlobally).not.toHaveBeenCalled();
  });
});

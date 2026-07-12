import { describe, expect, it } from "vitest";

import {
  PASSWORD_MIN_LENGTH,
  changePasswordSchema,
  resetPasswordSchema,
  resetRequestSchema
} from "./password-policy";

const validPassword = "a".repeat(PASSWORD_MIN_LENGTH);

describe("password reset request validation", () => {
  it("rejects an invalid email address", () => {
    expect(resetRequestSchema.safeParse({ email: "not-an-email" }).success).toBe(false);
  });
});

describe("password reset validation", () => {
  it("rejects a weak password", () => {
    expect(resetPasswordSchema.safeParse({
      newPassword: "too-short",
      confirmPassword: "too-short"
    }).success).toBe(false);
  });

  it("rejects mismatched passwords on the confirmation field", () => {
    const result = resetPasswordSchema.safeParse({
      newPassword: validPassword,
      confirmPassword: `${validPassword}!`
    });

    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues).toContainEqual(expect.objectContaining({
        message: "Passwords do not match.",
        path: ["confirmPassword"]
      }));
    }
  });

  it("accepts a valid confirmed password", () => {
    expect(resetPasswordSchema.safeParse({
      newPassword: validPassword,
      confirmPassword: validPassword
    }).success).toBe(true);
  });
});

describe("password change validation", () => {
  it("requires the current password", () => {
    expect(changePasswordSchema.safeParse({
      currentPassword: "",
      newPassword: validPassword,
      confirmPassword: validPassword
    }).success).toBe(false);
  });

  it("accepts current and confirmed new passwords", () => {
    expect(changePasswordSchema.safeParse({
      currentPassword: "current-password",
      newPassword: validPassword,
      confirmPassword: validPassword
    }).success).toBe(true);
  });
});

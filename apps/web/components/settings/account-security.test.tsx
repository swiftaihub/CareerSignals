// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountSecurity } from "./account-security";
import { DEMO_PASSWORD_CHANGE_MESSAGE } from "@/lib/password-policy";

vi.mock("@/app/(auth)/actions", () => ({
  changePasswordAction: vi.fn(async () => ({}))
}));

afterEach(cleanup);

describe("AccountSecurity", () => {
  it("prevents the demo account from opening password change", () => {
    render(<AccountSecurity preferencesDirty={false} readOnly />);

    expect(screen.getByRole("button", { name: "Change password" })).toBeDisabled();
    expect(screen.getByText(DEMO_PASSWORD_CHANGE_MESSAGE)).toBeVisible();
  });

  it("requires the current password in the authenticated change form", () => {
    render(<AccountSecurity preferencesDirty={false} readOnly={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Change password" }));

    expect(screen.getByLabelText("Current password")).toBeRequired();
    expect(screen.getByLabelText(/^New password/)).toBeRequired();
    expect(screen.getByLabelText("Confirm new password")).toBeRequired();
  });

  it("blocks password changes while preferences are unsaved", () => {
    render(<AccountSecurity preferencesDirty readOnly={false} />);

    expect(screen.getByRole("button", { name: "Change password" })).toBeDisabled();
    expect(screen.getByText(/Save or discard your unsaved preference changes/)).toBeVisible();
  });
});

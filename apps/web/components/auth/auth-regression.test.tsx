// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RegisterForm } from "./register-form";
import { AppSidebar } from "../layout/app-sidebar";
import { TopNav } from "../layout/top-nav";
import { withBasePath } from "@/lib/app-path";
import type { CurrentUser } from "@/lib/types";

vi.mock("@/app/(auth)/actions", () => ({
  logoutAction: vi.fn(),
  registerAction: vi.fn(async () => ({}))
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard"
}));

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_BASE_PATH", "/careersignals");
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

const user: CurrentUser = {
  user_uuid: "user-123",
  username: "career-user",
  role: "user",
  account_status: "active",
  created_at: "2026-01-01T00:00:00Z",
  is_demo: false
};

describe("existing authentication UI", () => {
  it("keeps registration fields and the sign-in return path", () => {
    render(<RegisterForm />);

    expect(screen.getByLabelText("Username")).toBeRequired();
    expect(screen.getByLabelText("Email")).toBeRequired();
    expect(screen.getByLabelText(/^Password/)).toBeRequired();
    expect(screen.getByRole("button", { name: "Create account" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });

  it("keeps logout available for an authenticated account", () => {
    render(<TopNav user={user} />);

    const button = screen.getByRole("button", { name: "Log out" });
    expect(button).toBeEnabled();
    expect(button.closest("form")).toHaveAttribute("action", withBasePath("/auth/logout"));
    expect(button.closest("form")).toHaveAttribute("method", "post");
  });

  it("links both authenticated brand marks to the mounted home page", () => {
    const { unmount } = render(<AppSidebar user={user} />);
    expect(screen.getByRole("link", { name: "CareerSignals home" }))
      .toHaveAttribute("href", "/careersignals");

    unmount();
    render(<TopNav user={user} />);
    expect(screen.getByRole("link", { name: "CareerSignals home" }))
      .toHaveAttribute("href", "/careersignals");
  });
});

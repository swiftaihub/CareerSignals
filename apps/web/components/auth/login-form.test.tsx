// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "./login-form";

vi.mock("@/app/(auth)/actions", () => ({
  demoAction: vi.fn(),
  loginAction: vi.fn(async () => ({}))
}));

afterEach(cleanup);

describe("LoginForm", () => {
  it("renders the password-recovery entry point without removing existing actions", () => {
    render(<LoginForm />);

    expect(screen.getByRole("link", { name: "Forgot password?" }))
      .toHaveAttribute("href", "/forgot-password");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Explore the read-only Demo" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Register" })).toHaveAttribute("href", "/register");
  });

  it("announces a password update after the server redirects to sign in", () => {
    render(<LoginForm initialSuccess="Password updated. Sign in again." />);

    expect(screen.getByRole("status")).toHaveTextContent("Password updated. Sign in again.");
  });
});

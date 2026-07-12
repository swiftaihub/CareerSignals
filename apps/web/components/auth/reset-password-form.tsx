"use client";

import Link from "next/link";
import { useActionState } from "react";

import {
  cancelPasswordRecoveryAction,
  resetPasswordAction,
  type AuthActionState
} from "@/app/(auth)/actions";
import { PASSWORD_MIN_LENGTH } from "@/lib/password-policy";

const INITIAL_STATE: AuthActionState = {};

export function ResetPasswordForm() {
  const [state, action, pending] = useActionState(
    resetPasswordAction,
    INITIAL_STATE
  );

  return (
    <div className="space-y-5">
      {state.error ? (
        <div
          className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900"
          role="alert"
        >
          {state.error}
        </div>
      ) : null}
      <form action={action} aria-busy={pending} className="space-y-4">
        <label className="block text-sm font-semibold" htmlFor="new-password">
          New password
          <input
            autoComplete="new-password"
            className="input mt-1"
            disabled={pending}
            id="new-password"
            minLength={PASSWORD_MIN_LENGTH}
            name="newPassword"
            required
            type="password"
          />
          <span className="mt-1 block text-xs font-normal text-muted-foreground">
            Use at least {PASSWORD_MIN_LENGTH} characters.
          </span>
        </label>
        <label className="block text-sm font-semibold" htmlFor="confirm-password">
          Confirm new password
          <input
            autoComplete="new-password"
            className="input mt-1"
            disabled={pending}
            id="confirm-password"
            minLength={PASSWORD_MIN_LENGTH}
            name="confirmPassword"
            required
            type="password"
          />
        </label>
        <button
          className="btn btn-primary w-full"
          disabled={pending}
          type="submit"
        >
          {pending ? "Updating password…" : "Update password"}
        </button>
      </form>

      <div className="grid gap-3 text-center text-sm">
        <Link className="font-semibold text-primary" href="/forgot-password">
          Request another reset email
        </Link>
        <form action={cancelPasswordRecoveryAction}>
          <button className="font-semibold text-muted-foreground hover:text-foreground" type="submit">
            Return to sign in
          </button>
        </form>
      </div>
    </div>
  );
}

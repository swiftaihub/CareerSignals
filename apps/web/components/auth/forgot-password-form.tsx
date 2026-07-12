"use client";

import Link from "next/link";
import { useActionState, useEffect, useState } from "react";

import {
  cancelPasswordRecoveryAction,
  forgotPasswordAction,
  type AuthActionState
} from "@/app/(auth)/actions";

const INITIAL_STATE: AuthActionState = {};

export function ForgotPasswordForm({ recoveryActive = false }: { recoveryActive?: boolean }) {
  const [state, action, pending] = useActionState(
    forgotPasswordAction,
    INITIAL_STATE
  );
  const [cooldownSeconds, setCooldownSeconds] = useState(0);

  useEffect(() => {
    if (!state.cooldownUntil) {
      setCooldownSeconds(0);
      return;
    }

    const updateCountdown = () => {
      setCooldownSeconds(Math.max(
        0,
        Math.ceil((state.cooldownUntil! - Date.now()) / 1000)
      ));
    };
    updateCountdown();
    const interval = window.setInterval(updateCountdown, 1000);
    return () => window.clearInterval(interval);
  }, [state.cooldownUntil]);

  const disabled = pending || cooldownSeconds > 0;
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
      {state.success ? (
        <div
          aria-live="polite"
          className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950"
          role="status"
        >
          {state.success}
        </div>
      ) : null}

      <form action={action} aria-busy={pending} className="space-y-4">
        <label className="block text-sm font-semibold" htmlFor="recovery-email">
          Email address
          <input
            autoComplete="email"
            className="input mt-1"
            disabled={disabled}
            id="recovery-email"
            name="email"
            required
            type="email"
          />
        </label>
        <button className="btn btn-primary w-full" disabled={disabled} type="submit">
          {pending
            ? "Sending reset link…"
            : cooldownSeconds > 0
              ? `Send again in ${cooldownSeconds}s`
              : "Send reset link"}
        </button>
      </form>

      <div className="text-center text-sm text-muted-foreground">
        {recoveryActive ? (
          <form action={cancelPasswordRecoveryAction}>
            <button className="font-semibold text-primary" type="submit">Back to sign in</button>
          </form>
        ) : (
          <Link className="font-semibold text-primary" href="/login">
            Back to sign in
          </Link>
        )}
      </div>
    </div>
  );
}

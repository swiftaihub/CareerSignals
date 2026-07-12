"use client";

import Link from "next/link";
import { useActionState } from "react";

import { demoAction, loginAction, type AuthActionState } from "@/app/(auth)/actions";

const initialState: AuthActionState = {};

export function LoginForm({
  nextPath,
  initialError,
  initialSuccess
}: {
  nextPath?: string;
  initialError?: string;
  initialSuccess?: string;
}) {
  const [state, action, pending] = useActionState(loginAction, initialState);
  const error = state.error || initialError;

  return (
    <div className="space-y-5">
      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900" role="alert">
          {error}
          {state.errorCode ? <div className="mt-1 text-xs font-semibold">{state.errorCode}</div> : null}
        </div>
      ) : null}
      {initialSuccess ? (
        <div
          aria-live="polite"
          className="fixed bottom-5 left-5 right-5 z-[60] max-w-md rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-medium text-emerald-950 shadow-2xl sm:left-auto"
          role="status"
        >
          {initialSuccess}
        </div>
      ) : null}
      <form action={action} className="space-y-4">
        <input type="hidden" name="next" value={nextPath || "/dashboard"} />
        <label className="block text-sm font-semibold">
          Username or email
          <input className="input mt-1" autoComplete="username" name="identifier" required />
        </label>
        <div>
          <div className="flex items-center justify-between gap-3">
            <label className="text-sm font-semibold" htmlFor="login-password">Password</label>
            <Link className="text-xs font-semibold text-primary" href="/forgot-password">Forgot password?</Link>
          </div>
          <input className="input mt-1" autoComplete="current-password" id="login-password" name="password" type="password" />
          <span className="mt-1 block text-xs font-normal text-muted-foreground">Leave blank when signing in as demo.</span>
        </div>
        <button className="btn btn-primary w-full" disabled={pending} type="submit">
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <div className="relative text-center text-xs uppercase text-muted-foreground">
        <span className="relative z-10 bg-card px-2">or</span>
        <span className="absolute inset-x-0 top-1/2 border-t border-border" />
      </div>
      <form action={demoAction}>
        <button className="btn w-full" type="submit">Explore the read-only Demo</button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Need an account? <Link className="font-semibold text-primary" href="/register">Register</Link>
      </p>
    </div>
  );
}

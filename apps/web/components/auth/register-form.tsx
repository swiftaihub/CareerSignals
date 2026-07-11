"use client";

import Link from "next/link";
import { useActionState } from "react";

import { registerAction, type AuthActionState } from "@/app/(auth)/actions";

export function RegisterForm() {
  const [state, action, pending] = useActionState(registerAction, {} as AuthActionState);
  return (
    <div className="space-y-5">
      {state.error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900" role="alert">
          {state.error}
          {state.errorCode ? <div className="mt-1 text-xs font-semibold">{state.errorCode}</div> : null}
        </div>
      ) : null}
      <form action={action} className="space-y-4">
        <label className="block text-sm font-semibold">
          Username
          <input className="input mt-1" autoComplete="username" name="username" required />
        </label>
        <label className="block text-sm font-semibold">
          Email
          <input className="input mt-1" autoComplete="email" name="email" required type="email" />
        </label>
        <label className="block text-sm font-semibold">
          Password
          <input className="input mt-1" autoComplete="new-password" minLength={10} name="password" required type="password" />
          <span className="mt-1 block text-xs font-normal text-muted-foreground">Use at least 10 characters.</span>
        </label>
        <button className="btn btn-primary w-full" disabled={pending} type="submit">
          {pending ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Already registered? <Link className="font-semibold text-primary" href="/login">Sign in</Link>
      </p>
    </div>
  );
}

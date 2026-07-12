import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";
import { readRecoverySession } from "@/lib/password-recovery-server";

export const dynamic = "force-dynamic";

export default async function ResetPasswordPage() {
  const recoveryState = await readRecoverySession();

  return (
    <AuthShell
      title="Choose a new password"
      description="Create a new password for your CareerSignals account."
    >
      {recoveryState.valid ? (
        <ResetPasswordForm />
      ) : (
        <div className="space-y-5">
          <p
            className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"
            role="alert"
          >
            This password reset session is missing, invalid, or expired. Request a new reset email to continue.
          </p>
          <Link className="btn btn-primary w-full" href="/forgot-password">
            Request another reset email
          </Link>
          <p className="text-center text-sm">
            <Link className="font-semibold text-muted-foreground" href="/login">
              Return to sign in
            </Link>
          </p>
        </div>
      )}
    </AuthShell>
  );
}

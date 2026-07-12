import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";
import { readRecoverySession } from "@/lib/password-recovery-server";

export default async function ForgotPasswordPage({
  searchParams
}: {
  searchParams: Promise<{ recovery_error?: string }>;
}) {
  const [params, recoveryState] = await Promise.all([
    searchParams,
    readRecoverySession()
  ]);
  const recoveryError = params.recovery_error === "invalid_or_expired"
    ? "This password reset link is invalid, expired, or has already been used. Request a new reset email."
    : null;

  return (
    <AuthShell
      title="Reset your password"
      description="Enter your account email and we’ll send secure password reset instructions."
    >
      {recoveryError ? (
        <p
          className="mb-5 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"
          role="alert"
        >
          {recoveryError}
        </p>
      ) : null}
      <ForgotPasswordForm recoveryActive={recoveryState.valid} />
    </AuthShell>
  );
}

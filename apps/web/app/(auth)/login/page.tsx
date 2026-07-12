import { redirect } from "next/navigation";

import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";
import { getCurrentUser } from "@/lib/auth";
import { safeRedirectPath } from "@/lib/navigation";
import {
  PASSWORD_CHANGE_SUCCESS_MESSAGE,
  PASSWORD_RESET_SUCCESS_MESSAGE
} from "@/lib/password-policy";

export default async function LoginPage({
  searchParams
}: {
  searchParams: Promise<{
    next?: string;
    error?: string;
    password_reset?: string;
    password_changed?: string;
  }>;
}) {
  const [params, user] = await Promise.all([searchParams, getCurrentUser()]);
  if (user?.account_status === "active") {
    redirect(safeRedirectPath(params.next));
  }
  const messages: Record<string, string> = {
    ACCOUNT_SUSPENDED: "This account is suspended. Contact an administrator.",
    ACCOUNT_DELETED: "This account is no longer available.",
    DEMO_UNAVAILABLE: "The Demo session is temporarily unavailable."
  };
  const success = params.password_reset === "success"
    ? PASSWORD_RESET_SUCCESS_MESSAGE
    : params.password_changed === "success"
      ? PASSWORD_CHANGE_SUCCESS_MESSAGE
      : undefined;
  return (
    <AuthShell title="Welcome back" description="Sign in with your username or email. Demo access does not require a password.">
      <LoginForm
        initialError={params.error ? messages[params.error] || "Please sign in again." : undefined}
        initialSuccess={success}
        nextPath={params.next}
      />
    </AuthShell>
  );
}

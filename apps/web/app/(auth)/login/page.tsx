import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";

export default async function LoginPage({
  searchParams
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const params = await searchParams;
  const messages: Record<string, string> = {
    ACCOUNT_SUSPENDED: "This account is suspended. Contact an administrator.",
    ACCOUNT_DELETED: "This account is no longer available.",
    DEMO_UNAVAILABLE: "The Demo session is temporarily unavailable."
  };
  return (
    <AuthShell title="Welcome back" description="Sign in with your username or email. Demo access does not require a password.">
      <LoginForm nextPath={params.next} initialError={params.error ? messages[params.error] || "Please sign in again." : undefined} />
    </AuthShell>
  );
}

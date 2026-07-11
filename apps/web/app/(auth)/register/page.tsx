import { AuthShell } from "@/components/auth/auth-shell";
import { RegisterForm } from "@/components/auth/register-form";

export default function RegisterPage() {
  return (
    <AuthShell title="Create your account" description="Registration creates a pending account. Your 30-day access period starts only after activation.">
      <RegisterForm />
    </AuthShell>
  );
}

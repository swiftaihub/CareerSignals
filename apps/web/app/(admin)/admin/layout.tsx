import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AccountProvider } from "@/components/auth/account-context";
import { AppShell } from "@/components/layout/app-shell";
import { getCurrentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/admin");
  if (user.account_status !== "active") redirect(user.account_status === "expired" ? "/account-expired" : "/pending");
  if (user.role !== "admin") redirect("/dashboard");

  return (
    <AccountProvider user={user}>
      <AppShell>{children}</AppShell>
    </AccountProvider>
  );
}

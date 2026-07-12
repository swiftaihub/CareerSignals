import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AccountProvider } from "@/components/auth/account-context";
import { getCurrentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function ProtectedLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.account_status === "pending") redirect("/pending");
  if (user.account_status === "expired") redirect("/account-expired");
  if (user.account_status === "suspended" || user.account_status === "deleted") {
    redirect(`/login?error=${encodeURIComponent(`ACCOUNT_${user.account_status.toUpperCase()}`)}`);
  }
  return <AccountProvider user={user}>{children}</AccountProvider>;
}

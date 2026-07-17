import { AuthShell } from "@/components/auth/auth-shell";
import { withBasePath } from "@/lib/app-path";
import { getCurrentUser } from "@/lib/auth";
import { formatDateTime } from "@/lib/formatters";

export default async function AccountExpiredPage() {
  const user = await getCurrentUser();
  return (
    <AuthShell title="Account access expired" description="Your data is preserved, but dashboard data and mutations are unavailable until access is extended.">
      <div className="space-y-4 text-sm">
        {user ? (
          <div className="rounded-md border border-border bg-muted/40 p-4">
            <div><strong>{user.username}</strong></div>
            <div className="mt-1 text-muted-foreground">Expired {formatDateTime(user.expires_at)}</div>
          </div>
        ) : null}
        <p>Contact a CareerSignals administrator to renew your entitlement.</p>
        <form action={withBasePath("/auth/logout")} method="post"><button className="btn w-full" type="submit">Log out</button></form>
      </div>
    </AuthShell>
  );
}

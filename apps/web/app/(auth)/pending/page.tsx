import Link from "next/link";

import { logoutAction } from "@/app/(auth)/actions";
import { AuthShell } from "@/components/auth/auth-shell";
import { getCurrentUser } from "@/lib/auth";

export default async function PendingPage({ searchParams }: { searchParams: Promise<{ registered?: string }> }) {
  const [user, params] = await Promise.all([getCurrentUser(), searchParams]);
  return (
    <AuthShell title="Activation pending" description="An administrator must activate your account before the 30-day entitlement begins.">
      <div className="space-y-4 text-sm">
        {params.registered ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-emerald-900">Registration completed successfully.</div> : null}
        {user ? <p>Signed in as <strong>{user.username}</strong>. Account status: <strong>{user.account_status}</strong>.</p> : <p>You may sign in later to check your account state.</p>}
        <div className="flex gap-3">
          <Link className="btn flex-1" href="/">Home</Link>
          {user ? <form action={logoutAction} className="flex-1"><button className="btn w-full" type="submit">Log out</button></form> : <Link className="btn btn-primary flex-1" href="/login">Sign in</Link>}
        </div>
      </div>
    </AuthShell>
  );
}

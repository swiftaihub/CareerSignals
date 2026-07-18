import Link from "next/link";
import type { ReactNode } from "react";

import { PublicHeader } from "@/components/home/public-header";
import { getCurrentUser } from "@/lib/auth";
import { withBasePath } from "@/lib/app-path";

export default async function PublicLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  return (
    <>
      <PublicHeader authenticated={Boolean(user)} />
      {children}
      <footer className="border-t border-slate-200 bg-white px-4 py-8 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <a className="flex items-center gap-2 font-bold text-slate-950" href={withBasePath("/")}>
            <span className="brand-mark brand-mark-small" aria-hidden="true"><span>CS</span></span>
            CareerSignals
          </a>
          <nav aria-label="Footer navigation" className="flex flex-wrap gap-x-6 gap-y-2">
            <Link className="hover:text-teal-800" href="/pricing">Pricing</Link>
            <Link className="hover:text-teal-800" href="/login">Log in</Link>
            <Link className="hover:text-teal-800" href="/register">Create your profile</Link>
          </nav>
          <p>Focused job intelligence, explained clearly.</p>
        </div>
      </footer>
    </>
  );
}

"use client";

import type { ReactNode } from "react";

import { useAccount } from "@/components/auth/account-context";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { TopNav } from "@/components/layout/top-nav";

export function AppShell({ children }: { children: ReactNode }) {
  const user = useAccount();
  return (
    <div className="min-h-screen lg:flex">
      <AppSidebar user={user} />
      <div className="min-w-0 flex-1">
        <TopNav user={user} />
        <main className="mx-auto max-w-7xl px-4 py-6 md:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

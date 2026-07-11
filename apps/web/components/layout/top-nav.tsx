"use client";

import Link from "next/link";
import { ExternalLink, LogOut, Menu } from "lucide-react";

import { logoutAction } from "@/app/(auth)/actions";
import { adminItems, navItems } from "@/components/layout/app-sidebar";
import type { CurrentUser } from "@/lib/types";

export function TopNav({ user }: { user?: CurrentUser | null }) {
  const mobileItems = user?.role === "admin" ? [...navItems, ...adminItems] : navItems;
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/85 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground">
            CareerSignals Dashboard
          </div>
          <div className="text-sm text-muted-foreground">
            User-scoped insights over the shared CareerSignals job universe
          </div>
        </div>
        <div className="flex items-center gap-2">
          {user ? (
            <div className="hidden text-right sm:block">
              <div className="text-sm font-semibold">{user.username}</div>
              <div className="text-xs text-muted-foreground">
                {user.is_demo ? "Demo · read-only" : user.role === "admin" ? "Administrator" : `${user.remaining_days ?? 0} days remaining`}
              </div>
            </div>
          ) : null}
          <details className="relative lg:hidden">
            <summary className="btn btn-ghost list-none" aria-label="Open navigation">
              <Menu className="h-4 w-4" />Menu
            </summary>
            <nav className="absolute right-0 mt-2 grid min-w-56 gap-1 rounded-lg border border-border bg-card p-2 shadow-xl">
              {mobileItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Link className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium hover:bg-muted" href={item.href} key={item.href}>
                    <Icon className="h-4 w-4" />{item.label}
                  </Link>
                );
              })}
            </nav>
          </details>
          <Link className="btn btn-primary" href="/jobs">
            Explore Jobs
            <ExternalLink className="h-4 w-4" />
          </Link>
          {user ? (
            <form action={logoutAction}>
              <button className="btn btn-ghost" type="submit" title="Log out">
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Log out</span>
              </button>
            </form>
          ) : null}
        </div>
      </div>
    </header>
  );
}

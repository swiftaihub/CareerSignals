"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  BriefcaseBusiness,
  Building2,
  Gauge,
  Home,
  Settings,
  ShieldCheck,
  Sparkles
} from "lucide-react";

import type { CurrentUser } from "@/lib/types";
import { cn } from "@/lib/utils";

export const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/top-matches", label: "Top Matches", icon: Sparkles },
  { href: "/skill-gap", label: "Skill Gap", icon: BarChart3 },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/settings", label: "Settings", icon: Settings }
];

export const adminItems = [
  { href: "/admin", label: "Admin Dashboard", icon: ShieldCheck },
  { href: "/admin/users", label: "User Management", icon: BriefcaseBusiness },
  { href: "/admin/audit", label: "Audit Logs", icon: BarChart3 }
];

export function AppSidebar({ user }: { user?: CurrentUser | null }) {
  const pathname = usePathname();
  const items = user?.role === "admin" ? [...navItems, ...adminItems] : navItems;
  return (
    <aside className="hidden w-64 shrink-0 border-r border-border bg-card/95 px-4 py-5 lg:block">
      <Link href="/" className="flex items-center gap-3 rounded-lg px-2 py-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
          CS
        </div>
        <div>
          <div className="text-sm font-bold">CareerSignals</div>
          <div className="text-xs text-muted-foreground">Personal intelligence</div>
        </div>
      </Link>

      <nav className="mt-6 space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition hover:bg-muted hover:text-foreground",
                pathname === item.href || (item.href !== "/" && pathname.startsWith(`${item.href}/`))
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

import Link from "next/link";
import { ArrowRight, LayoutDashboard, LogIn, Play } from "lucide-react";

import { demoAction } from "@/app/(auth)/actions";
import { withBasePath } from "@/lib/app-path";

import { HOME_ROUTES } from "./home-content";

export function PublicHeader({ authenticated = false }: { authenticated?: boolean }) {
  return (
    <header className="public-header">
      <div className="mx-auto flex h-16 max-w-[90rem] items-center justify-between gap-3 px-4 sm:px-6 lg:px-10">
        <a className="group flex min-w-0 items-center gap-2.5 font-bold text-slate-950" href={withBasePath(HOME_ROUTES.home)} aria-label="CareerSignals home">
          <span className="brand-mark" aria-hidden="true"><span>CS</span></span>
          <span className="hidden text-[0.95rem] tracking-[-0.02em] min-[380px]:inline">CareerSignals</span>
        </a>

        <nav aria-label="Public navigation" className="flex min-w-0 items-center gap-1.5 sm:gap-2">
          <a className="btn btn-ghost hidden md:inline-flex" href={withBasePath(HOME_ROUTES.howItWorks)}>How it works</a>
          <Link className="btn btn-ghost hidden sm:inline-flex" href={HOME_ROUTES.pricing}>Pricing</Link>
          {authenticated ? (
            <Link className="btn btn-primary header-primary" href={HOME_ROUTES.dashboard}>
              <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Open Dashboard</span>
              <span className="sm:hidden">Dashboard</span>
            </Link>
          ) : (
            <>
              <Link className="btn btn-ghost h-10 w-10 px-0 sm:w-auto sm:px-4" href={HOME_ROUTES.login} aria-label="Log in">
                <LogIn className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">Log in</span>
              </Link>
              <Link className="btn btn-primary header-primary" href={HOME_ROUTES.register}>
                <span className="hidden sm:inline">Create profile</span>
                <span className="sm:hidden">Start</span>
                <ArrowRight className="hidden h-4 w-4 sm:block" aria-hidden="true" />
              </Link>
              <form action={demoAction} className="hidden xl:block">
                <button className="btn btn-ghost" type="submit"><Play className="h-3.5 w-3.5 fill-current" aria-hidden="true" /> Demo</button>
              </form>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

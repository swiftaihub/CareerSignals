import Link from "next/link";

import { demoAction } from "@/app/(auth)/actions";

export function PublicHeader({ authenticated = false }: { authenticated?: boolean }) {
  return (
    <header className="border-b border-border bg-background/90 px-4 py-3 backdrop-blur md:px-6">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <Link className="flex items-center gap-2 font-bold" href="/"><span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">CS</span>CareerSignals</Link>
        <nav className="flex items-center gap-2">
          <Link className="btn btn-ghost hidden sm:inline-flex" href="/pricing">Pricing</Link>
          {authenticated ? (
            <Link className="btn btn-primary" href="/dashboard">Open Dashboard</Link>
          ) : (
            <>
              <Link className="btn" href="/login">Sign In</Link>
              <Link className="btn btn-primary" href="/register">Register</Link>
              <form action={demoAction} className="hidden md:block"><button className="btn" type="submit">Explore Demo</button></form>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

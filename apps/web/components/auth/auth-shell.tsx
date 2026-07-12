import Link from "next/link";
import type { ReactNode } from "react";

export function AuthShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <main className="landing-mesh flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-soft md:p-8">
        <Link href="/" className="inline-flex items-center gap-2 text-sm font-bold text-primary">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">CS</span>
          CareerSignals
        </Link>
        <h1 className="mt-6 text-3xl font-bold">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
        <div className="mt-6">{children}</div>
      </div>
    </main>
  );
}

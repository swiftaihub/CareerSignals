import Link from "next/link";
import { ArrowRight, BarChart3, CheckCircle2, Database, Play, Sparkles } from "lucide-react";

import { demoAction } from "@/app/(auth)/actions";

const metrics = [
  ["Jobs Processed", "342", "+48 today"],
  ["Top Matches", "27", "8 excellent"],
  ["Skill Coverage", "86%", "SQL, Python, dbt"],
  ["Source Refresh", "Automatic", "Platform schedule"]
];

const matches = [
  ["Senior Analytics Engineer", "Fintech platform", "94"],
  ["Product Data Scientist", "AI workflow suite", "91"],
  ["Credit Risk Analyst", "Banking analytics", "86"]
];

const flow = ["Ingest", "Model", "Score", "Review"];

export function HeroSection() {
  return (
    <section className="landing-mesh surface-grid relative overflow-hidden border-b border-border">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 pb-12 pt-14 md:px-6 lg:grid-cols-[0.95fr_1.05fr] lg:px-8 lg:pb-16 lg:pt-20">
        <div className="flex flex-col justify-center">
          <div className="mb-4 inline-flex w-fit items-center gap-2 rounded-full border border-teal-200 bg-white/80 px-3 py-1 text-xs font-semibold text-teal-800 shadow-sm">
            <Sparkles className="h-3.5 w-3.5" />
            Job-search intelligence for high-fit decisions
          </div>
          <h1 className="text-4xl font-bold tracking-normal text-foreground md:text-6xl">
            CareerSignals
          </h1>
          <p className="mt-5 max-w-2xl text-xl leading-8 text-foreground">
            Turn scattered job postings into a scored, explainable, daily decision queue.
          </p>
          <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
            CareerSignals refreshes source job data automatically, then uses your personal configuration
            to filter, categorize, and score the shared job universe—without exposing data credentials.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="btn btn-primary" href="/register">
              Create Account
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link className="btn" href="/login">Log in</Link>
            <form action={demoAction}><button className="btn" type="submit"><Play className="h-4 w-4" />Explore Demo</button></form>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            Demo sign-in: Username <strong>demo</strong>; password not required. Demo results are fixed and read-only.
          </p>
        </div>

        <div className="rounded-lg border border-border bg-white/90 p-4 shadow-soft backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
            <div>
              <div className="text-xs font-semibold uppercase text-muted-foreground">
                CareerSignals Intelligence Console
              </div>
              <div className="mt-1 text-lg font-bold text-foreground">Daily role review</div>
            </div>
            <div className="badge border-emerald-200 bg-emerald-50 text-emerald-800">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Pipeline ready
            </div>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {metrics.map(([label, value, detail]) => (
              <div key={label} className="rounded-md border border-border bg-background/90 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
                  <BarChart3 className="h-3.5 w-3.5 text-primary" />
                </div>
                <div className="mt-2 text-2xl font-bold text-foreground">{value}</div>
                <div className="mt-1 truncate text-xs text-muted-foreground">{detail}</div>
              </div>
            ))}
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_0.65fr]">
            <div className="rounded-md border border-border bg-background/90 p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-xs font-semibold uppercase text-muted-foreground">Top match queue</div>
                <span className="text-xs font-medium text-primary">Sorted by fit</span>
              </div>
              <div className="space-y-2">
                {matches.map(([role, company, score]) => (
                  <div key={role} className="flex items-center justify-between gap-3 rounded-md bg-white px-3 py-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-foreground">{role}</div>
                      <div className="truncate text-xs text-muted-foreground">{company}</div>
                    </div>
                    <div className="badge shrink-0 border-teal-200 bg-teal-50 text-teal-800">{score}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-md border border-border bg-foreground p-3 text-background">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase text-teal-100">
                <Database className="h-3.5 w-3.5" />
                Pipeline Flow
              </div>
              <div className="mt-4 space-y-2">
                {flow.map((stage, index) => (
                  <div key={stage} className="flex items-center gap-2 text-sm">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-400 text-xs font-bold text-slate-950">
                      {index + 1}
                    </span>
                    <span>{stage}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

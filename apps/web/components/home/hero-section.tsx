import Link from "next/link";
import { ArrowRight, BarChart3, Database, Sparkles } from "lucide-react";

export function HeroSection() {
  return (
    <section className="relative overflow-hidden border-b border-border">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 md:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8 lg:py-20">
        <div className="flex flex-col justify-center">
          <div className="mb-4 inline-flex w-fit items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-800">
            <Sparkles className="h-3.5 w-3.5" />
            Personal job-search intelligence platform
          </div>
          <h1 className="text-4xl font-bold text-foreground md:text-6xl">CareerSignal</h1>
          <p className="mt-5 max-w-3xl text-xl leading-8 text-muted-foreground">
            A configurable job-search intelligence platform that turns scattered postings into
            structured, scored, and prioritized career opportunities.
          </p>
          <p className="mt-5 max-w-3xl text-base leading-7 text-muted-foreground">
            CareerSignal helps data professionals move beyond manual job tracking by combining
            configurable job categories, automated ingestion, role matching, skill-gap analysis,
            company prioritization, and application tracking in one analytics-ready dashboard.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="btn btn-primary" href="/dashboard">
              Open Dashboard
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link className="btn" href="/jobs">
              Explore Jobs
            </Link>
            <Link className="btn" href="/top-matches">
              View Top Matches
            </Link>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 shadow-soft">
          <div className="rounded-md border border-border bg-background p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-semibold uppercase text-muted-foreground">
                  Illustrative Product Preview
                </div>
                <div className="mt-1 text-xl font-bold">Highest-fit roles</div>
              </div>
              <div className="rounded-md bg-primary p-2 text-primary-foreground">
                <BarChart3 className="h-5 w-5" />
              </div>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              {[
                ["Total Jobs", "342"],
                ["Top Matches", "27"],
                ["Avg Score", "82"]
              ].map(([label, value]) => (
                <div key={label} className="rounded-md border border-border bg-card p-3">
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="mt-1 text-2xl font-bold">{value}</div>
                </div>
              ))}
            </div>
            <div className="mt-5 space-y-3">
              {[
                ["Senior Analytics Engineer", "Acme Health", "94"],
                ["Product Data Scientist", "Northstar AI", "91"],
                ["Credit Risk Analyst", "Metro Finance", "86"]
              ].map(([role, company, score]) => (
                <div key={role} className="flex items-center justify-between rounded-md border border-border bg-card p-3">
                  <div>
                    <div className="font-semibold">{role}</div>
                    <div className="text-xs text-muted-foreground">{company}</div>
                  </div>
                  <div className="badge border-emerald-200 bg-emerald-50 text-emerald-800">{score}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {["Connectors", "dbt Marts", "FastAPI"].map((label) => (
              <div key={label} className="flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-2 text-sm">
                <Database className="h-4 w-4 text-primary" />
                {label}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

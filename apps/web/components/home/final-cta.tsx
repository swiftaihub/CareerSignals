import Link from "next/link";
import { ArrowRight, Play, Sparkles } from "lucide-react";

export function FinalCta() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 md:px-6 lg:px-8">
      <div className="rounded-lg border border-slate-800 bg-foreground p-8 text-background shadow-soft">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 text-sm font-semibold text-teal-200">
              <Sparkles className="h-4 w-4" />
              CareerSignal is ready for the next review cycle.
            </div>
            <h2 className="mt-3 text-3xl font-bold md:text-4xl">
              Move from job-search noise to a daily decision queue.
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              Open the dashboard, review high-fit roles, or refresh the pipeline when your quota is available.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link className="btn border-white bg-white text-foreground hover:bg-neutral-100" href="/dashboard">
              Open Dashboard
            </Link>
            <Link className="btn border-teal-200 bg-teal-600 text-white hover:bg-teal-700" href="/top-matches">
              View Top Matches
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link className="btn border-slate-600 bg-slate-900 text-white hover:bg-slate-800" href="/settings">
              <Play className="h-4 w-4" />
              Run Pipeline
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

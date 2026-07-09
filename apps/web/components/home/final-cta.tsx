import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";

export function FinalCta() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-14 md:px-6 lg:px-8">
      <div className="rounded-lg border border-border bg-foreground p-8 text-background shadow-soft">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 text-sm font-semibold text-teal-200">
              <Sparkles className="h-4 w-4" />
              Start exploring your highest-fit roles.
            </div>
            <h2 className="mt-3 text-3xl font-bold">Turn job-search noise into a focused review queue.</h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link className="btn border-white bg-white text-foreground hover:bg-neutral-100" href="/dashboard">
              Go to Dashboard
            </Link>
            <Link className="btn border-teal-200 bg-teal-600 text-white hover:bg-teal-700" href="/top-matches">
              View Top Matches
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

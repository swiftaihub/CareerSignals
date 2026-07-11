import Link from "next/link";
import { ArrowRight, Play, Sparkles } from "lucide-react";

import { demoAction } from "@/app/(auth)/actions";

export function FinalCta() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-16 md:px-6 lg:px-8">
      <div className="rounded-lg border border-slate-800 bg-foreground p-8 text-background shadow-soft">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 text-sm font-semibold text-teal-200">
              <Sparkles className="h-4 w-4" />
              CareerSignals is ready for the next review cycle.
            </div>
            <h2 className="mt-3 text-3xl font-bold md:text-4xl">
              Move from job-search noise to a daily decision queue.
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              Source jobs refresh automatically. Sign in to generate personal matching from your configuration.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link className="btn border-white bg-white text-foreground hover:bg-neutral-100" href="/register">
              Register
            </Link>
            <Link className="btn border-teal-200 bg-teal-600 text-white hover:bg-teal-700" href="/login">
              Log in
              <ArrowRight className="h-4 w-4" />
            </Link>
            <form action={demoAction}><button className="btn border-slate-600 bg-slate-900 text-white hover:bg-slate-800" type="submit"><Play className="h-4 w-4" />Explore Demo</button></form>
          </div>
        </div>
      </div>
    </section>
  );
}

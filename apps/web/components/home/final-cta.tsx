import Link from "next/link";
import { ArrowRight, LogIn, Play, Sparkles } from "lucide-react";

import { demoAction } from "@/app/(auth)/actions";

import { HOME_ROUTES } from "./home-content";
import { SectionReveal } from "./section-reveal";

export function FinalCta() {
  return (
    <section className="px-4 pb-20 sm:px-6 lg:px-8 lg:pb-28">
      <SectionReveal className="final-cta mx-auto max-w-7xl">
        <div className="final-cta-grid" aria-hidden="true" />
        <div className="relative mx-auto max-w-3xl text-center">
          <div className="section-eyebrow section-eyebrow-dark justify-center">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" /> Start with your strongest signals
          </div>
          <h2 className="mt-5 text-balance text-3xl font-bold tracking-[-0.035em] text-white sm:text-5xl">
            Your next great role should be easier to see.
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-7 text-slate-300">
            Build your profile, review your strongest matches, and turn a noisy job market into a focused plan.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row sm:flex-wrap">
            <Link className="btn landing-cta border-white bg-white text-slate-950 hover:bg-teal-50 sm:h-12 sm:px-5" href={HOME_ROUTES.register}>
              Create your profile <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <form action={demoAction}>
              <button className="btn landing-cta w-full border-slate-600 bg-slate-800 text-white hover:bg-slate-700 sm:h-12 sm:w-auto sm:px-5" type="submit">
                <Play className="h-4 w-4 fill-current" aria-hidden="true" /> Explore the demo
              </button>
            </form>
          </div>
          <Link className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-teal-200 underline-offset-4 hover:text-white hover:underline" href={HOME_ROUTES.login}>
            <LogIn className="h-4 w-4" aria-hidden="true" /> Already have an account? Log in.
          </Link>
        </div>
      </SectionReveal>
    </section>
  );
}

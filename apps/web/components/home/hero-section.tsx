import Image from "next/image";
import Link from "next/link";
import { ArrowRight, CheckCircle2, LogIn, Play, Sparkles } from "lucide-react";

import { demoAction } from "@/app/(auth)/actions";

import { FloatingProductPreview } from "./floating-product-preview";
import { HOME_ROUTES } from "./home-content";

export function HeroSection() {
  return (
    <section className="landing-hero landing-mesh surface-grid relative overflow-hidden border-b border-slate-200/70">
      <div className="hero-orb hero-orb-one" aria-hidden="true" />
      <div className="hero-orb hero-orb-two" aria-hidden="true" />
      <div className="mx-auto grid max-w-[90rem] gap-12 px-4 pb-20 pt-14 sm:px-6 lg:grid-cols-[0.88fr_1.12fr] lg:items-center lg:px-10 lg:pb-24 lg:pt-20 xl:gap-16">
        <div className="relative z-10 max-w-2xl">
          <div className="hero-enter hero-delay-1 section-eyebrow">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            Personalized job intelligence
          </div>
          <h1 className="hero-enter hero-delay-2 mt-5 text-balance text-[clamp(2.65rem,6vw,5.6rem)] font-bold leading-[0.96] tracking-[-0.055em] text-slate-950">
            Find the roles worth your time.
          </h1>
          <p className="hero-enter hero-delay-3 mt-6 max-w-xl text-pretty text-base leading-7 text-slate-600 sm:text-lg sm:leading-8">
            CareerSignals turns scattered job postings into a ranked, explainable queue built around your skills,
            goals, and preferences—so you can spend less time searching and more time applying with confidence.
          </p>
          <div className="hero-enter hero-delay-4 mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Link className="btn btn-primary landing-cta sm:h-12 sm:px-5" href={HOME_ROUTES.register}>
              Create your profile
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <form action={demoAction}>
              <button className="btn landing-cta w-full sm:h-12 sm:w-auto sm:px-5" type="submit">
                <Play className="h-4 w-4 fill-current" aria-hidden="true" />
                Explore live demo
              </button>
            </form>
            <Link className="btn btn-ghost landing-cta sm:h-12 sm:px-4" href={HOME_ROUTES.login}>
              <LogIn className="h-4 w-4" aria-hidden="true" />
              Log in
            </Link>
          </div>
          <p className="hero-enter hero-delay-5 mt-7 flex max-w-xl items-start gap-2 text-sm leading-6 text-slate-600">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" aria-hidden="true" />
            Fresh job data. Personal matching. Clear reasons behind every score.
          </p>
        </div>

        <div className="hero-visual-enter relative mx-auto w-full max-w-3xl">
          <div className="hero-illustration-shell">
            <Image
              alt="Professional using CareerSignals beside floating job match cards and analytics"
              className="hero-illustration"
              height={1024}
              priority
              sizes="(max-width: 1023px) 94vw, 55vw"
              src="/illustrations/hero-career-dashboard.webp"
              width={1536}
            />
          </div>
          <FloatingProductPreview />
        </div>
      </div>
    </section>
  );
}

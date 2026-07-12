import { Check, DatabaseZap, KeyRound, LockKeyhole, ShieldCheck, UserRoundCheck } from "lucide-react";

import { TRUST_INDICATORS } from "./home-content";
import { SectionReveal } from "./section-reveal";

const icons = [KeyRound, UserRoundCheck, LockKeyhole, ShieldCheck];

export function TrustSection() {
  return (
    <section className="marketing-section trust-section overflow-hidden">
      <div className="trust-orb" aria-hidden="true" />
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-[0.92fr_1.08fr] lg:items-center">
          <SectionReveal>
            <div className="section-eyebrow section-eyebrow-dark">Personal by design</div>
            <h2 className="section-title text-white">Your preferences stay personal. Your job data stays fresh.</h2>
            <p className="section-copy text-slate-300">
              Shared job data refreshes on a platform schedule, while your profile is used to generate user-scoped
              matching results behind the authenticated application boundary.
            </p>
          </SectionReveal>

          <div className="grid gap-3 sm:grid-cols-2">
            {TRUST_INDICATORS.map((indicator, index) => {
              const Icon = icons[index];
              return (
                <SectionReveal className="trust-card" delay={index * 70} key={indicator}>
                  <span className="trust-icon"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                  <span className="font-semibold text-white">{indicator}</span>
                  <Check className="ml-auto h-4 w-4 text-teal-300" aria-hidden="true" />
                </SectionReveal>
              );
            })}
          </div>
        </div>

        <SectionReveal className="technology-strip" delay={120}>
          <span className="flex items-center gap-2 text-sm font-semibold text-white">
            <DatabaseZap className="h-4 w-4 text-teal-300" aria-hidden="true" /> Powered by
          </span>
          {['Next.js', 'FastAPI', 'Supabase', 'dbt', 'MotherDuck'].map((technology) => (
            <span className="technology-pill" key={technology}>{technology}</span>
          ))}
        </SectionReveal>
      </div>
    </section>
  );
}

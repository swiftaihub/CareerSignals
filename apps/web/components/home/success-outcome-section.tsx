import Image from "next/image";
import { ArrowRight, CircleCheckBig } from "lucide-react";

import { SectionReveal } from "./section-reveal";

export function SuccessOutcomeSection() {
  return (
    <section className="marketing-section success-section overflow-hidden">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 sm:px-6 lg:grid-cols-[1.08fr_0.92fr] lg:items-center lg:px-8">
        <SectionReveal className="order-2 lg:order-1">
          <div className="relative">
            <div className="illustration-glow illustration-glow-amber" aria-hidden="true" />
            <Image
              alt="Professional happily viewing a positive next-step notification on a laptop"
              className="relative h-auto w-full"
              height={1024}
              loading="lazy"
              sizes="(max-width: 1023px) 94vw, 52vw"
              src="/illustrations/offer-success.webp"
              width={1536}
            />
          </div>
        </SectionReveal>
        <SectionReveal className="order-1 lg:order-2" delay={100}>
          <div className="section-eyebrow">From shortlist to next step</div>
          <h2 className="section-title">Keep your search moving forward.</h2>
          <p className="section-copy">
            Spend less time sorting through noise and more time preparing for the opportunities that deserve your attention.
          </p>
          <div className="mt-7 inline-flex items-center gap-3 rounded-2xl border border-teal-100 bg-white p-4 shadow-sm">
            <CircleCheckBig className="h-6 w-6 text-teal-700" aria-hidden="true" />
            <div>
              <p className="text-sm font-bold text-slate-950">A clearer next action</p>
              <p className="mt-0.5 text-xs text-slate-500">Prioritize, prepare, and progress at your pace.</p>
            </div>
            <ArrowRight className="ml-2 h-4 w-4 text-teal-700" aria-hidden="true" />
          </div>
        </SectionReveal>
      </div>
    </section>
  );
}

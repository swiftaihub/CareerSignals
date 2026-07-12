import Image from "next/image";
import { Focus, Gauge, SlidersHorizontal } from "lucide-react";

import { NOISE_TO_SIGNAL_VALUES } from "./home-content";
import { SectionReveal } from "./section-reveal";

const icons = [Focus, Gauge, SlidersHorizontal];

export function NoiseToSignalSection() {
  return (
    <section className="marketing-section overflow-hidden" id="why-careersignals">
      <div className="mx-auto grid max-w-7xl gap-12 px-4 sm:px-6 lg:grid-cols-[0.88fr_1.12fr] lg:items-center lg:px-8">
        <SectionReveal>
          <div className="section-eyebrow">From noise to signal</div>
          <h2 className="section-title">Stop opening fifty tabs to find three good roles.</h2>
          <p className="section-copy">
            CareerSignals collects the market, removes duplicates, extracts the details that matter, and brings the
            strongest opportunities to the top.
          </p>

          <div className="mt-8 space-y-3">
            {NOISE_TO_SIGNAL_VALUES.map((item, index) => {
              const Icon = icons[index];
              return (
                <SectionReveal className="value-row" delay={index * 80} key={item.title}>
                  <div className="value-icon"><Icon className="h-5 w-5" aria-hidden="true" /></div>
                  <div>
                    <h3 className="text-base font-bold text-slate-950">{item.title}</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-600">{item.body}</p>
                  </div>
                </SectionReveal>
              );
            })}
          </div>
        </SectionReveal>

        <SectionReveal className="relative" delay={100}>
          <div className="illustration-glow" aria-hidden="true" />
          <Image
            alt="Scattered job cards passing through a signal filter into three ranked opportunities"
            className="relative h-auto w-full"
            height={887}
            loading="lazy"
            sizes="(max-width: 1023px) 94vw, 54vw"
            src="/illustrations/noise-to-signal.webp"
            width={1774}
          />
        </SectionReveal>
      </div>
    </section>
  );
}

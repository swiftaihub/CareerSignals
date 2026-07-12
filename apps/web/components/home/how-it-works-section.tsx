"use client";

import Image from "next/image";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { BriefcaseBusiness, ListChecks, RefreshCw, UserRoundCheck } from "lucide-react";

import { cn } from "@/lib/utils";

import { HOW_IT_WORKS_STEPS } from "./home-content";

const icons = [UserRoundCheck, RefreshCw, BriefcaseBusiness, ListChecks];

export function HowItWorksSection() {
  const stepRefs = useRef<Array<HTMLElement | null>>([]);
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        const index = Number((visible.target as HTMLElement).dataset.stepIndex);
        if (Number.isInteger(index)) setActiveStep(index);
      },
      { rootMargin: "-28% 0px -38%", threshold: [0.2, 0.5, 0.75] }
    );

    stepRefs.current.forEach((step) => {
      if (step) observer.observe(step);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <section className="marketing-section how-section border-y border-slate-200/80 bg-white" id="how-it-works">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <div className="section-eyebrow">How it works</div>
          <h2 className="section-title">Your search, organized into four clear steps.</h2>
        </div>

        <div className="mt-12 grid gap-10 lg:grid-cols-[1.08fr_0.92fr] lg:gap-16">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <div className="story-visual">
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">Personal matching flow</span>
                <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-bold text-teal-800">
                  Step {activeStep + 1} of 4
                </span>
              </div>
              <Image
                alt="Candidate profile and preferences moving through four analysis stages into scored job cards"
                className="mt-6 h-auto w-full"
                height={929}
                loading="lazy"
                sizes="(max-width: 1023px) 94vw, 51vw"
                src="/illustrations/personal-matching-flow.webp"
                width={1693}
              />
              <div className="story-progress" style={{ "--story-progress": `${((activeStep + 1) / 4) * 100}%` } as CSSProperties}>
                <div className="story-progress-fill" />
                <div className="relative flex justify-between">
                  {HOW_IT_WORKS_STEPS.map((step, index) => (
                    <span
                      className={cn("story-node", index <= activeStep && "is-active", index === activeStep && "is-current")}
                      key={step.title}
                    >
                      {index + 1}
                    </span>
                  ))}
                </div>
              </div>
              <div className="mt-5 flex items-center gap-3 rounded-xl border border-teal-100 bg-teal-50/70 p-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-teal-700 shadow-sm">
                  {(() => {
                    const ActiveIcon = icons[activeStep];
                    return <ActiveIcon className="h-4 w-4" aria-hidden="true" />;
                  })()}
                </div>
                <div>
                  <p className="text-xs font-semibold text-teal-700">Active stage</p>
                  <p className="text-sm font-bold text-slate-950">{HOW_IT_WORKS_STEPS[activeStep].title}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="timeline-list">
            {HOW_IT_WORKS_STEPS.map((step, index) => {
              const Icon = icons[index];
              return (
                <article
                  aria-current={index === activeStep ? "step" : undefined}
                  className={cn("timeline-step", index === activeStep && "is-active")}
                  data-step-index={index}
                  key={step.title}
                  ref={(element) => { stepRefs.current[index] = element; }}
                >
                  <div className="timeline-marker">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">Step {index + 1}</p>
                    <h3 className="mt-2 text-xl font-bold text-slate-950">{step.title}</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-600 sm:text-base">{step.body}</p>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

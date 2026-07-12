"use client";

import Image from "next/image";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import {
  BadgeDollarSign,
  BriefcaseBusiness,
  Building2,
  ListChecks,
  MapPin,
  RefreshCw,
  SlidersHorizontal,
  UserRoundCheck
} from "lucide-react";

import { cn } from "@/lib/utils";

import { HOW_IT_WORKS_STEPS } from "./home-content";

const icons = [UserRoundCheck, RefreshCw, BriefcaseBusiness, ListChecks];
const matchingSignals = [
  { label: "Skills & seniority", icon: UserRoundCheck },
  { label: "Salary expectations", icon: BadgeDollarSign },
  { label: "Location & work model", icon: MapPin },
  { label: "Industry & visa signals", icon: Building2 }
];
const constellationStages = ["Profile sun", "Market planet", "Evidence moon", "Application launch"];

export function HowItWorksSection() {
  const stepRefs = useRef<Array<HTMLElement | null>>([]);
  const [scrollActiveStep, setScrollActiveStep] = useState(0);
  const [interactiveStep, setInteractiveStep] = useState<number | null>(null);
  const activeStep = interactiveStep ?? scrollActiveStep;

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        const index = Number((visible.target as HTMLElement).dataset.stepIndex);
        if (Number.isInteger(index)) setScrollActiveStep(index);
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
          <div className="story-sticky-stack lg:sticky lg:top-20 lg:self-start">
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
              <div className="story-signals">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-500">Signals in view</p>
                    <p className="mt-1 text-sm font-bold text-slate-950">The evidence behind each ranking</p>
                  </div>
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-950 text-white">
                    <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
                  </span>
                </div>
                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  {matchingSignals.map((signal) => {
                    const SignalIcon = signal.icon;
                    return (
                      <div className="story-signal-chip" key={signal.label}>
                        <SignalIcon className="h-3.5 w-3.5 text-teal-700" aria-hidden="true" />
                        {signal.label}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
            <div className="story-constellation">
              <div className="constellation-grid" aria-hidden="true" />
              <div className="relative z-10 flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-cyan-200">Signal constellation</p>
                  <p className="mt-1 max-w-xs text-sm font-semibold leading-6 text-white">
                    Every stage brings the right evidence into focus.
                  </p>
                </div>
                <span className="rounded-full border border-white/15 bg-white/10 px-2.5 py-1 text-xs font-bold text-cyan-100">
                  0{activeStep + 1}
                </span>
              </div>

              <div
                className="constellation-canvas"
                aria-label={`Active signal stage: ${HOW_IT_WORKS_STEPS[activeStep].title}`}
              >
                <div className={cn("constellation-universe", `is-step-${activeStep + 1}`)} aria-hidden="true">
                  <div className="solar-orbit" />
                  <div className="celestial-sun" />
                  <div className="celestial-planet"><span /></div>
                  <div className="moon-orbit" />
                  <div className="celestial-moon"><span /></div>
                  <div className="celestial-rocket"><span /></div>
                </div>
                <div className="constellation-caption">
                  <span>Step {activeStep + 1}</span>
                  <strong>{constellationStages[activeStep]}</strong>
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
                  onBlur={() => setInteractiveStep(null)}
                  onFocus={() => setInteractiveStep(index)}
                  onMouseEnter={() => setInteractiveStep(index)}
                  onMouseLeave={() => setInteractiveStep(null)}
                  ref={(element) => { stepRefs.current[index] = element; }}
                  tabIndex={0}
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

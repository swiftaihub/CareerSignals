import { ArrowUpRight, BarChart3, CircleCheck, Gauge, KanbanSquare, SearchCheck, Target } from "lucide-react";

import { PRODUCT_CAPABILITIES } from "./home-content";
import { SectionReveal } from "./section-reveal";

const capabilityIcons = [Target, SearchCheck, BarChart3, KanbanSquare];

export function ProductPreviewSection() {
  return (
    <section className="marketing-section overflow-hidden" id="product-preview">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <SectionReveal className="mx-auto max-w-3xl text-center">
          <div className="section-eyebrow justify-center">Built for daily decisions</div>
          <h2 className="section-title">Know what to apply to—and why.</h2>
          <p className="section-copy mx-auto">
            CareerSignals gives you a focused view of the opportunities, evidence, and next actions that matter today.
          </p>
        </SectionReveal>

        <div className="product-composition mt-12">
          <SectionReveal className="product-main-panel" delay={60}>
            <div className="product-panel-header">
              <div>
                <p className="product-kicker">Today&apos;s review</p>
                <h3 className="mt-1 text-lg font-bold text-slate-950">Top Matches</h3>
              </div>
              <span className="status-chip"><CircleCheck className="h-3.5 w-3.5" aria-hidden="true" /> Ready to review</span>
            </div>
            <div className="mt-5 space-y-3">
              {[
                ["Senior Analytics Engineer", "94", "Strong skills · Remote"],
                ["Product Data Scientist", "91", "Salary aligned · Hybrid"],
                ["Risk Analytics Lead", "86", "Industry match · Visa signal"]
              ].map(([role, score, detail], index) => (
                <div className="preview-job-row" key={role}>
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="job-rank">{index + 1}</span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-bold text-slate-950">{role}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">{detail}</p>
                    </div>
                  </div>
                  <span className="preview-score">{score}</span>
                </div>
              ))}
            </div>
          </SectionReveal>

          <SectionReveal className="product-side-panel" delay={130}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="product-kicker">Explainable score</p>
                <h3 className="mt-1 text-base font-bold text-slate-950">Evidence of fit</h3>
              </div>
              <Gauge className="h-5 w-5 text-teal-700" aria-hidden="true" />
            </div>
            <div className="mt-5 space-y-3">
              {[["Skills", "92%"], ["Preferences", "88%"], ["Salary", "Aligned"]].map(([label, value], index) => (
                <div key={label}>
                  <div className="flex justify-between text-xs font-semibold text-slate-600"><span>{label}</span><span>{value}</span></div>
                  <div className="metric-track"><span style={{ width: `${92 - index * 9}%` }} /></div>
                </div>
              ))}
            </div>
          </SectionReveal>

          <SectionReveal className="product-side-panel" delay={200}>
            <p className="product-kicker">Application pipeline</p>
            <h3 className="mt-1 text-base font-bold text-slate-950">Keep momentum visible</h3>
            <div className="mt-5 grid grid-cols-3 gap-2">
              {[["Saved", "12"], ["Applied", "7"], ["Interview", "2"]].map(([label, value]) => (
                <div className="pipeline-stat" key={label}><strong>{value}</strong><span>{label}</span></div>
              ))}
            </div>
          </SectionReveal>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {PRODUCT_CAPABILITIES.map((item, index) => {
            const Icon = capabilityIcons[index];
            return (
              <SectionReveal className="capability-card" delay={index * 70} key={item.title}>
                <div className="flex items-center justify-between">
                  <span className="capability-icon"><Icon className="h-5 w-5" aria-hidden="true" /></span>
                  <ArrowUpRight className="card-arrow h-4 w-4 text-slate-400" aria-hidden="true" />
                </div>
                <h3 className="mt-5 text-base font-bold text-slate-950">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{item.body}</p>
              </SectionReveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

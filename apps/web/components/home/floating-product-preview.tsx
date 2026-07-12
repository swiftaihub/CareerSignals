import { BarChart3, CheckCircle2, Sparkles } from "lucide-react";

import { DEMO_PREVIEW_LABEL, HERO_MATCHES } from "./home-content";

export function FloatingProductPreview() {
  return (
    <div className="hero-product-panel" aria-label="Illustrative CareerSignals top matches preview">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200/80 pb-3">
        <div>
          <div className="text-[0.65rem] font-bold uppercase tracking-[0.16em] text-teal-700">
            {DEMO_PREVIEW_LABEL}
          </div>
          <div className="mt-1 flex items-center gap-2 text-sm font-bold text-slate-950">
            <Sparkles className="h-4 w-4 text-amber-500" aria-hidden="true" />
            Top Matches
          </div>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[0.65rem] font-bold text-emerald-800">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
          Analysis complete
        </span>
      </div>

      <div className="mt-3 space-y-2">
        {HERO_MATCHES.map((match, index) => (
          <article className={index === 0 ? "match-row match-row-featured" : "match-row"} key={match.role}>
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-xs font-bold text-slate-950 sm:text-sm">{match.role}</h3>
              <p className="mt-0.5 truncate text-[0.65rem] text-slate-500">{match.company}</p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {match.signals.map((signal) => (
                  <span className="signal-chip" key={signal}>{signal}</span>
                ))}
              </div>
            </div>
            <div className="score-ring" aria-label={`${match.score} match score`}>
              <span>{match.score}</span>
            </div>
          </article>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2 text-[0.65rem] font-semibold text-slate-500">
        <BarChart3 className="h-3.5 w-3.5 text-teal-600" aria-hidden="true" />
        Ranked using your selected priorities
      </div>
    </div>
  );
}

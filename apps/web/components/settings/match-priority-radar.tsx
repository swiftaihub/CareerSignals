"use client";

import { useState } from "react";
import { LockKeyhole, SlidersHorizontal, Unlock } from "lucide-react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip
} from "recharts";

import { SectionCard } from "@/components/shared/section-card";
import {
  MATCH_PRIORITY_KEYS,
  MATCH_PRIORITY_LABELS,
  MATCH_PRIORITY_PRESETS,
  redistributeMatchPriority,
  totalMatchPriorities,
  type MatchPriorityPreset
} from "@/lib/preferences";
import type { MatchPriorities, MatchPriorityKey } from "@/lib/types";

const SHORT_LABELS: Record<MatchPriorityKey, string> = {
  title_match: "Title",
  required_skill_match: "Skills",
  industry_match: "Industry",
  salary_match: "Salary",
  work_arrangement_match: "Work Style",
  visa_signal_match: "Visa"
};

const PRESET_LABELS: Record<MatchPriorityPreset, string> = {
  balanced: "Balanced",
  skills_first: "Skills First",
  title_industry_first: "Title & Industry First"
};

export function MatchPriorityRadar({
  value,
  disabled,
  onChange
}: {
  value: MatchPriorities;
  disabled: boolean;
  onChange: (value: MatchPriorities) => void;
}) {
  const [locked, setLocked] = useState<Partial<Record<MatchPriorityKey, boolean>>>({});
  const total = totalMatchPriorities(value);
  const radarData = MATCH_PRIORITY_KEYS.map((key) => ({
    factor: SHORT_LABELS[key],
    percentage: value[key]
  }));

  function update(key: MatchPriorityKey, next: number) {
    onChange(redistributeMatchPriority(value, key, next, locked));
  }

  function applyPreset(preset: MatchPriorityPreset) {
    setLocked({});
    onChange({ ...MATCH_PRIORITY_PRESETS[preset] });
  }

  return (
    <SectionCard
      className="mt-6 scroll-mt-24"
      title="Match Priorities"
      description="Shape how CareerSignals ranks opportunities. Every adjustment is redistributed in whole percentages so the total always remains 100%."
    >
      <div id="match-priorities">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background/70 p-4">
          <div className="flex items-center gap-3"><span className="rounded-lg bg-teal-50 p-2 text-primary"><SlidersHorizontal className="h-5 w-5" /></span><div><div className="text-sm font-semibold">Choose a starting point</div><div className="text-xs text-muted-foreground">Presets remain fully editable.</div></div></div>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(PRESET_LABELS) as MatchPriorityPreset[]).map((preset) => (
              <button className="btn h-9 px-3 text-xs" disabled={disabled} key={preset} type="button" onClick={() => applyPreset(preset)}>{PRESET_LABELS[preset]}</button>
            ))}
          </div>
        </div>

        <div className="mt-5 grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
          <div className="rounded-xl border border-border bg-background/70 p-4">
            <div className="flex items-center justify-between gap-3"><h3 className="text-sm font-semibold">Priority shape</h3><span className={`badge ${total === 100 ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800"}`}>{total}% total</span></div>
            <div aria-label="Interactive match priority radar. Focus a point and use arrow keys to adjust it." className="mt-2 h-80 w-full" role="group">
              <ResponsiveContainer height="100%" width="100%">
                <RadarChart data={radarData} margin={{ top: 24, right: 36, bottom: 24, left: 36 }}>
                  <PolarGrid stroke="#cbd5e1" />
                  <PolarAngleAxis dataKey="factor" tick={{ fill: "#475569", fontSize: 12 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "#64748b", fontSize: 10 }} tickCount={5} />
                  <Tooltip formatter={(next) => [`${next}%`, "Importance"]} />
                  <Radar
                    dataKey="percentage"
                    dot={(dot) => {
                      const index = typeof dot.index === "number" ? dot.index : 0;
                      const key = MATCH_PRIORITY_KEYS[index] || MATCH_PRIORITY_KEYS[0];
                      const isLocked = Boolean(locked[key]);
                      const current = value[key];
                      function adjust(delta: number) {
                        if (!disabled && !isLocked) update(key, current + delta);
                      }
                      return (
                        <circle
                          aria-label={`${MATCH_PRIORITY_LABELS[key]} ${current} percent${isLocked ? ", locked" : ". Use arrow keys to adjust."}`}
                          aria-valuemax={100}
                          aria-valuemin={0}
                          aria-valuenow={current}
                          cx={dot.cx}
                          cy={dot.cy}
                          fill={isLocked ? "#64748b" : "#0f766e"}
                          r={6}
                          role="slider"
                          stroke="white"
                          strokeWidth={2}
                          style={{ cursor: disabled || isLocked ? "not-allowed" : "pointer" }}
                          tabIndex={disabled || isLocked ? -1 : 0}
                          onClick={(event) => adjust(event.shiftKey ? -5 : 5)}
                          onKeyDown={(event) => {
                            if (event.key === "ArrowUp" || event.key === "ArrowRight") { event.preventDefault(); adjust(1); }
                            else if (event.key === "ArrowDown" || event.key === "ArrowLeft") { event.preventDefault(); adjust(-1); }
                            else if (event.key === "PageUp") { event.preventDefault(); adjust(5); }
                            else if (event.key === "PageDown") { event.preventDefault(); adjust(-5); }
                          }}
                        />
                      );
                    }}
                    fill="#0f766e"
                    fillOpacity={0.28}
                    isAnimationActive={false}
                    name="Importance"
                    stroke="#0f766e"
                    strokeWidth={2}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-center text-xs leading-5 text-muted-foreground">Click a chart point to add 5% (Shift-click subtracts 5%), focus it and use arrow keys, or use the sliders and percentage fields.</p>
          </div>

          <div className="space-y-3">
            {MATCH_PRIORITY_KEYS.map((key) => {
              const isLocked = Boolean(locked[key]);
              return (
                <div className="rounded-xl border border-border bg-card p-4" key={key}>
                  <div className="flex items-center justify-between gap-3">
                    <label className="text-sm font-semibold" htmlFor={`priority-${key}`}>{MATCH_PRIORITY_LABELS[key]}</label>
                    <div className="flex items-center gap-2">
                      <label className="sr-only" htmlFor={`priority-${key}-number`}>{MATCH_PRIORITY_LABELS[key]} percentage</label>
                      <div className="relative">
                        <input
                          aria-label={`${MATCH_PRIORITY_LABELS[key]} percentage`}
                          className="input h-9 w-20 pr-7 text-right"
                          disabled={disabled || isLocked}
                          id={`priority-${key}-number`}
                          max={100}
                          min={0}
                          type="number"
                          value={value[key]}
                          onChange={(event) => update(key, Number(event.target.value))}
                        />
                        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                      </div>
                      <button
                        aria-label={`${isLocked ? "Unlock" : "Lock"} ${MATCH_PRIORITY_LABELS[key]}`}
                        aria-pressed={isLocked}
                        className="btn h-9 w-9 px-0"
                        disabled={disabled}
                        title={isLocked ? "Unlock this value" : "Keep this value fixed while adjusting others"}
                        type="button"
                        onClick={() => setLocked((current) => ({ ...current, [key]: !current[key] }))}
                      >
                        {isLocked ? <LockKeyhole className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <input
                    aria-valuetext={`${value[key]} percent`}
                    className="mt-3 h-2 w-full cursor-pointer accent-teal-700 disabled:cursor-not-allowed"
                    disabled={disabled || isLocked}
                    id={`priority-${key}`}
                    max={100}
                    min={0}
                    step={1}
                    type="range"
                    value={value[key]}
                    onChange={(event) => update(key, Number(event.target.value))}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

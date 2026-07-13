"use client";

import { useState } from "react";

import type { DashboardFunnel } from "@/lib/types";

const NUMBER_FORMATTER = new Intl.NumberFormat("en-US");
const PERCENT_FORMATTER = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1
});

const STAGE_DEFINITIONS = [
  { key: "total_global_jobs", label: "Total Global Jobs", color: "hsl(var(--primary))" },
  { key: "total_user_jobs", label: "Jobs for You", color: "hsl(var(--accent))" },
  { key: "total_applied_jobs", label: "Applied Jobs", color: "hsl(var(--success))" },
  { key: "total_interviews", label: "Interviews", color: "hsl(var(--warning))" }
] as const;

export interface FunnelStage {
  key: keyof DashboardFunnel;
  label: string;
  count: number;
  color: string;
  previousCount: number | null;
  conversionFromPrevious: number | null;
  shareOfTotal: number | null;
  dropOffFromPrevious: number | null;
}

export function buildFunnelStages(data: DashboardFunnel): FunnelStage[] {
  const total = data.total_global_jobs;

  return STAGE_DEFINITIONS.map((definition, index) => {
    const count = data[definition.key];
    const previousCount = index === 0 ? null : data[STAGE_DEFINITIONS[index - 1].key];

    return {
      ...definition,
      count,
      previousCount,
      conversionFromPrevious:
        previousCount === null || previousCount === 0 ? null : count / previousCount,
      shareOfTotal: total === 0 ? null : count / total,
      dropOffFromPrevious: previousCount === null ? null : previousCount - count
    };
  });
}

function formatPercentage(value: number | null) {
  return value === null ? "Not available" : `${PERCENT_FORMATTER.format(value * 100)}%`;
}

function stageAriaLabel(stage: FunnelStage) {
  const conversion = stage.previousCount === null
    ? "No previous-stage conversion"
    : `${formatPercentage(stage.conversionFromPrevious)} conversion from the previous stage`;
  return `${stage.label}: ${NUMBER_FORMATTER.format(stage.count)} jobs. ${conversion}. ${formatPercentage(stage.shareOfTotal)} of total global jobs.`;
}

function FunnelTooltip({ stage }: { stage: FunnelStage }) {
  return (
    <div
      className="rounded-lg border border-border bg-card p-4 text-sm shadow-soft"
      id={`funnel-tooltip-${stage.key}`}
      role="tooltip"
    >
      <div className="flex items-center justify-between gap-4">
        <p className="font-semibold text-foreground">{stage.label}</p>
        <p className="text-base font-bold text-foreground">{NUMBER_FORMATTER.format(stage.count)}</p>
      </div>
      <dl className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
        <div>
          <dt>From previous</dt>
          <dd className="mt-0.5 font-semibold text-foreground">
            {stage.previousCount === null
              ? "Baseline"
              : formatPercentage(stage.conversionFromPrevious)}
          </dd>
        </div>
        <div>
          <dt>Share of global</dt>
          <dd className="mt-0.5 font-semibold text-foreground">
            {formatPercentage(stage.shareOfTotal)}
          </dd>
        </div>
        <div>
          <dt>Drop-off</dt>
          <dd className="mt-0.5 font-semibold text-foreground">
            {stage.dropOffFromPrevious === null
              ? "Baseline"
              : NUMBER_FORMATTER.format(stage.dropOffFromPrevious)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function JobSearchFunnel({ data }: { data: DashboardFunnel }) {
  const stages = buildFunnelStages(data);
  const [focusedKey, setFocusedKey] = useState<FunnelStage["key"] | null>(null);
  const [hoveredKey, setHoveredKey] = useState<FunnelStage["key"] | null>(null);
  const activeKey = focusedKey ?? hoveredKey;
  const activeStage = stages.find((stage) => stage.key === activeKey) ?? null;
  const maximumWidth = 330;
  const minimumWidth = 58;
  const centerX = 180;
  const total = Math.max(data.total_global_jobs, 0);
  const widths = stages.map((stage, index) => {
    if (index === 0) return maximumWidth;
    if (total === 0) return minimumWidth;
    const ratio = Math.min(Math.max(stage.count / total, 0), 1);
    return minimumWidth + (maximumWidth - minimumWidth) * Math.sqrt(ratio);
  });

  return (
    <div>
      <div className="funnel-chart-enter grid h-72 grid-cols-[minmax(0,1fr)_minmax(8rem,0.85fr)] gap-3">
        <svg
          aria-label="Job search funnel. Focus a stage for conversion details."
          className="h-full w-full"
          preserveAspectRatio="none"
          role="group"
          viewBox="0 0 360 320"
        >
          {stages.map((stage, index) => {
            const y = 10 + index * 75;
            const upperWidth = widths[index];
            const lowerWidth = widths[index + 1] ?? minimumWidth * 0.72;
            const points = [
              `${centerX - upperWidth / 2},${y}`,
              `${centerX + upperWidth / 2},${y}`,
              `${centerX + lowerWidth / 2},${y + 62}`,
              `${centerX - lowerWidth / 2},${y + 62}`
            ].join(" ");
            const active = activeKey === stage.key;

            return (
              <polygon
                aria-describedby={active ? `funnel-tooltip-${stage.key}` : undefined}
                aria-label={stageAriaLabel(stage)}
                className="cursor-pointer outline-none transition duration-200"
                fill={stage.color}
                key={stage.key}
                opacity={active ? 1 : 0.86}
                points={points}
                role="img"
                stroke={active ? "hsl(var(--foreground))" : "hsl(var(--card))"}
                strokeWidth={active ? 3 : 2}
                style={{ vectorEffect: "non-scaling-stroke" }}
                tabIndex={0}
                onBlur={() => setFocusedKey(null)}
                onFocus={() => setFocusedKey(stage.key)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setFocusedKey(null);
                    setHoveredKey(null);
                    event.currentTarget.blur();
                  }
                }}
                onMouseEnter={() => setHoveredKey(stage.key)}
                onMouseLeave={() => setHoveredKey(null)}
              />
            );
          })}
        </svg>

        <div aria-hidden="true" className="grid grid-rows-4">
          {stages.map((stage) => (
            <div className="flex min-w-0 flex-col justify-center" key={stage.key}>
              <span className="text-xs font-semibold leading-4 text-foreground sm:text-sm">
                {stage.label}
              </span>
              <span className="mt-0.5 text-base font-bold text-muted-foreground sm:text-lg">
                {NUMBER_FORMATTER.format(stage.count)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div aria-live="polite" className="mt-3 min-h-32">
        {activeStage ? (
          <FunnelTooltip stage={activeStage} />
        ) : (
          <div className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-border bg-card/70 p-4 text-center text-xs text-muted-foreground">
            Hover over or focus a stage to see conversion and drop-off details.
          </div>
        )}
      </div>
    </div>
  );
}

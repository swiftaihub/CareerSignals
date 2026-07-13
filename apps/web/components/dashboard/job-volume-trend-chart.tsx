"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps
} from "recharts";

import { EmptyState } from "@/components/shared/empty-state";
import type { JobCountTimeSeriesPoint } from "@/lib/types";

const NUMBER_FORMATTER = new Intl.NumberFormat("en-US");

export const JOB_VOLUME_SERIES = [
  { dataKey: "global_jobs", name: "Global Jobs", color: "hsl(var(--primary))" },
  { dataKey: "user_jobs", name: "Jobs for You", color: "hsl(var(--accent))" },
  { dataKey: "applied_jobs", name: "Applied Jobs", color: "hsl(var(--success))" }
] as const satisfies ReadonlyArray<{
  dataKey: keyof Omit<JobCountTimeSeriesPoint, "date">;
  name: string;
  color: string;
}>;

function formatCount(value: number | null | undefined) {
  return typeof value === "number" ? NUMBER_FORMATTER.format(value) : "Not available";
}

export function JobVolumeTooltip({
  active,
  date,
  point
}: {
  active?: boolean;
  date?: string;
  point?: JobCountTimeSeriesPoint;
}) {
  if (!active || !date || !point) return null;

  return (
    <div
      className="min-w-48 rounded-lg border border-border bg-card p-3 text-sm shadow-soft"
      role="tooltip"
    >
      <p className="font-semibold text-foreground">{date}</p>
      <dl className="mt-2 space-y-1.5">
        {JOB_VOLUME_SERIES.map((series) => (
          <div className="flex items-center justify-between gap-5" key={series.dataKey}>
            <dt className="inline-flex items-center gap-2 text-muted-foreground">
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: series.color }}
              />
              {series.name}
            </dt>
            <dd className="font-semibold text-foreground">{formatCount(point[series.dataKey])}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function RechartsTooltip({
  active,
  label,
  payload
}: TooltipContentProps) {
  const point = payload.find((entry) => entry.payload)?.payload as JobCountTimeSeriesPoint | undefined;
  return (
    <JobVolumeTooltip
      active={active}
      date={typeof label === "string" ? label : undefined}
      point={point}
    />
  );
}

export function JobVolumeTrendChart({ data }: { data: JobCountTimeSeriesPoint[] }) {
  const chartData = data.filter((point) =>
    JOB_VOLUME_SERIES.some((series) => typeof point[series.dataKey] === "number")
  );

  if (!chartData.length) {
    return (
      <div className="min-h-80 [&>div]:min-h-80">
        <EmptyState
          title="No job volume history yet"
          description="Daily history will appear after the first reliable analytics snapshot is recorded."
        />
      </div>
    );
  }

  return (
    <>
      <div
        aria-label="Daily job volume line chart with Global Jobs, Jobs for You, and Applied Jobs series."
        className="h-80 min-h-80 w-full"
        role="img"
      >
        <ResponsiveContainer height="100%" width="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 16 }}>
            <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              interval="preserveStartEnd"
              minTickGap={32}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
              tickFormatter={(value) => String(value)}
            />
            <YAxis
              allowDecimals={false}
              label={{
                value: "Number of Jobs",
                angle: -90,
                position: "insideLeft",
                fill: "hsl(var(--muted-foreground))",
                fontSize: 11
              }}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
              width={62}
            />
            <Tooltip
              content={RechartsTooltip}
              cursor={{ stroke: "hsl(var(--muted-foreground))", strokeDasharray: "4 4" }}
              filterNull={false}
            />
            <Legend verticalAlign="top" height={36} />
            {JOB_VOLUME_SERIES.map((series) => (
              <Line
                activeDot={{ r: 5, strokeWidth: 2 }}
                connectNulls={false}
                dataKey={series.dataKey}
                dot={{ r: 2, strokeWidth: 1 }}
                isAnimationActive={false}
                key={series.dataKey}
                name={series.name}
                stroke={series.color}
                strokeWidth={2.5}
                type="linear"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <table className="sr-only">
        <caption>Daily job volume values</caption>
        <thead>
          <tr>
            <th>Date</th>
            {JOB_VOLUME_SERIES.map((series) => <th key={series.dataKey}>{series.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {chartData.map((point) => (
            <tr key={point.date}>
              <th>{point.date}</th>
              {JOB_VOLUME_SERIES.map((series) => (
                <td key={series.dataKey}>{formatCount(point[series.dataKey])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

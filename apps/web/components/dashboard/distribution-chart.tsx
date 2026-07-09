"use client";

import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip
} from "recharts";

import type { DistributionRow } from "@/lib/types";

const COLORS = ["#0f766e", "#0891b2", "#16a34a", "#ca8a04", "#dc2626", "#6b7280"];

export function DistributionChart({ data }: { data: DistributionRow[] }) {
  const chartData = data.filter((row) => row.count > 0);

  return (
    <div className="grid min-h-64 gap-4 md:grid-cols-[1fr_180px]">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              dataKey="count"
              nameKey="label"
              innerRadius={58}
              outerRadius={92}
              paddingAngle={2}
            >
              {chartData.map((entry, index) => (
                <Cell key={entry.label} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="space-y-2 self-center">
        {chartData.map((entry, index) => (
          <div key={entry.label} className="flex items-center justify-between gap-3 text-sm">
            <span className="inline-flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: COLORS[index % COLORS.length] }}
              />
              {entry.label}
            </span>
            <span className="font-semibold">{entry.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

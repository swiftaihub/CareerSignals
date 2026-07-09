"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { CategorySummaryRow } from "@/lib/types";

export function CategoryChart({ data }: { data: CategorySummaryRow[] }) {
  const chartData = data.slice(0, 8).map((row) => ({
    category: row.category_name,
    jobs: row.jobs_found || 0,
    score: row.average_match_score || 0
  }));

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ left: 0, right: 12, top: 8, bottom: 32 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="category"
            angle={-20}
            interval={0}
            height={58}
            tick={{ fontSize: 11 }}
            textAnchor="end"
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Bar dataKey="jobs" fill="#0f766e" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

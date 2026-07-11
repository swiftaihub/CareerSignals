"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { TimeSeriesPoint } from "@/lib/types";

export function AdminTrendChart({ data, color = "#0f766e" }: { data?: TimeSeriesPoint[]; color?: string }) {
  const rows = (data || []).map((row) => ({
    label: row.date || row.label || String(row.hour ?? ""),
    value: row.value ?? row.count ?? row.total ?? 0,
    failed: row.failed
  }));
  const hasFailures = rows.some((row) => row.failed !== undefined);
  if (!rows.length) return <div className="flex h-56 items-center justify-center text-sm text-muted-foreground">No data in this period.</div>;
  return <div className="h-56"><ResponsiveContainer width="100%" height="100%"><LineChart data={rows}><CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="label" fontSize={11} /><YAxis allowDecimals={false} fontSize={11} /><Tooltip />{hasFailures ? <Legend /> : null}<Line name={hasFailures ? "Total" : "Value"} type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} />{hasFailures ? <Line name="Failed" type="monotone" dataKey="failed" stroke="#dc2626" strokeWidth={2} dot={false} /> : null}</LineChart></ResponsiveContainer></div>;
}

"use client";

export interface AdminDateRange { start_date: string; end_date: string; }

export function AdminDateFilter({ value, onChange }: { value: AdminDateRange; onChange: (value: AdminDateRange) => void }) {
  return <div className="flex flex-wrap items-end gap-3 rounded-md border border-border bg-card p-3"><label className="text-xs font-semibold uppercase text-muted-foreground">Start date<input className="input mt-1 normal-case" type="date" value={value.start_date} onChange={(event) => onChange({ ...value, start_date: event.target.value })} /></label><label className="text-xs font-semibold uppercase text-muted-foreground">End date<input className="input mt-1 normal-case" type="date" value={value.end_date} onChange={(event) => onChange({ ...value, end_date: event.target.value })} /></label></div>;
}

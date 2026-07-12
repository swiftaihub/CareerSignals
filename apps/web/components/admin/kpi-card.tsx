import type { ReactNode } from "react";

export function KpiCard({ label, value, helper, icon }: { label: string; value: ReactNode; helper?: string; icon?: ReactNode }) {
  return <article className="rounded-lg border border-border bg-card p-4 shadow-soft"><div className="flex items-start justify-between gap-3"><div><div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div><div className="mt-2 text-2xl font-bold">{value}</div></div>{icon}</div>{helper ? <p className="mt-2 text-xs text-muted-foreground">{helper}</p> : null}</article>;
}

import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  helper,
  icon
}: {
  label: string;
  value: ReactNode;
  helper?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-soft">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
          <div className="mt-2 text-2xl font-bold text-foreground">{value}</div>
        </div>
        {icon ? (
          <div className="rounded-md border border-border bg-muted p-2 text-primary">{icon}</div>
        ) : null}
      </div>
      {helper ? <p className="mt-3 text-xs text-muted-foreground">{helper}</p> : null}
    </div>
  );
}

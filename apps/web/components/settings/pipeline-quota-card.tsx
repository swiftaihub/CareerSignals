import { Gauge, RefreshCcw } from "lucide-react";

import type { PipelineQuota } from "@/lib/types";

function refreshLabel(remaining: number) {
  if (remaining === 1) {
    return "1 refresh available";
  }
  return `${remaining} refreshes available`;
}

function resetDate(value?: string) {
  if (!value) {
    return "the configured quota window";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "the configured quota window";
  }
  const day = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(date);
  return day;
}

export function PipelineQuotaCard({ quota }: { quota?: PipelineQuota | null }) {
  const unlimited = quota?.limit === null;
  const remaining = quota?.remaining ?? 0;
  const limit = quota?.limit ?? 0;
  const used = quota?.used ?? 0;

  return (
    <section className="rounded-lg border border-border bg-card p-5 shadow-soft">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground">
            Personal Pipeline Quota
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">
            {unlimited ? "Unlimited refreshes" : remaining === 0 ? "0 refreshes available" : refreshLabel(remaining)}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {unlimited
              ? `${used} successful refreshes completed in the current window.`
              : remaining === 0
              ? "No personal refreshes remain in the current quota window."
              : `${used} of ${limit} refreshes used in the current window.`}
          </p>
        </div>
        <div className="rounded-md bg-teal-50 p-2 text-primary">
          <Gauge className="h-5 w-5" />
        </div>
      </div>

      <div className="mt-4 rounded-md border border-border bg-background p-3 text-sm">
        <div className="flex items-center gap-2 font-medium text-foreground">
          <RefreshCcw className="h-4 w-4 text-primary" />
          Resets {resetDate(quota?.resets_at)}
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${unlimited ? 0 : Math.min((used / Math.max(limit, 1)) * 100, 100)}%` }}
          />
        </div>
      </div>
    </section>
  );
}

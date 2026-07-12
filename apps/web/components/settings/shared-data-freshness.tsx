import { AlertTriangle, CheckCircle2, Database } from "lucide-react";

import { SectionCard } from "@/components/shared/section-card";
import { formatDateTime } from "@/lib/formatters";
import type { DataFreshness } from "@/lib/types";

function freshnessAge(value?: string | null) {
  if (!value) return "Unknown";
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return "Unknown";
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60_000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function SharedDataFreshness({ freshness }: { freshness: DataFreshness | null }) {
  return (
    <SectionCard
      className="mt-6 scroll-mt-24"
      title="Global shared job-data freshness"
      description="Read-only platform status for the shared job universe used by every personal match refresh."
    >
      <div id="shared-data-freshness">
        {!freshness ? (
          <p className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">Freshness details are unavailable.</p>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {[
                ["Overall status", freshness.overall.status],
                ["Last refresh", formatDateTime(freshness.overall.last_successful_refresh_at)],
                ["Freshness age", freshnessAge(freshness.overall.last_successful_refresh_at)],
                ["Data as of", formatDateTime(freshness.overall.data_as_of)]
              ].map(([label, value]) => (
                <div className="rounded-lg border border-border bg-background p-4" key={label}>
                  <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
                  <div className="mt-2 text-base font-semibold text-foreground">{value}</div>
                </div>
              ))}
            </div>
            <div className={`mt-4 flex gap-2 rounded-lg border p-3 text-sm ${freshness.overall.is_stale ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}>
              {freshness.overall.is_stale ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />}
              {freshness.overall.is_stale ? "Shared job data may be stale; your refresh will use the latest published snapshot." : "Shared job data is ready for personal matching."}
            </div>
            <div className="mt-4 table-shell overflow-x-auto">
              <table className="data-table min-w-[760px]">
                <thead><tr><th>Data source</th><th>Last refreshed</th><th>Status</th><th>Freshness age</th><th>Record count</th></tr></thead>
                <tbody>
                  {freshness.sources.map((source) => (
                    <tr key={source.source_name}>
                      <td><span className="inline-flex items-center gap-2 font-semibold"><Database className="h-4 w-4 text-primary" />{source.source_name}</span></td>
                      <td>{formatDateTime(source.last_successful_refresh_at)}</td>
                      <td><span className="badge border-border bg-background">{source.status}</span></td>
                      <td>{freshnessAge(source.last_successful_refresh_at)}</td>
                      <td>{source.records_retained?.toLocaleString() ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </SectionCard>
  );
}

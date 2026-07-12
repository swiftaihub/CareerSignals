import { CheckCircle2, Clock3, Database, RefreshCcw, Sparkles, UserRoundCheck } from "lucide-react";

import { SectionCard } from "@/components/shared/section-card";
import { formatDateTime } from "@/lib/formatters";
import type { DataFreshness, PipelineQuota, UserPipelineRun } from "@/lib/types";

function OverviewCard({
  icon,
  eyebrow,
  value,
  detail,
  children
}: {
  icon: React.ReactNode;
  eyebrow: string;
  value: React.ReactNode;
  detail: string;
  children?: React.ReactNode;
}) {
  return (
    <article className="rounded-xl border border-border bg-background/80 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{eyebrow}</div>
          <div className="mt-2 text-xl font-bold text-foreground">{value}</div>
        </div>
        <span className="rounded-lg border border-teal-100 bg-teal-50 p-2 text-primary">{icon}</span>
      </div>
      <p className="mt-2 text-sm leading-5 text-muted-foreground">{detail}</p>
      {children}
    </article>
  );
}

export function SettingsOverview({
  freshness,
  runs,
  quota,
  profileCompleteness
}: {
  freshness: DataFreshness | null;
  runs: UserPipelineRun[];
  quota: PipelineQuota | null;
  profileCompleteness: number;
}) {
  const lastRun = runs[0];
  const successful = runs.find((run) => run.status === "completed");
  const healthySources = freshness?.sources.filter((source) => source.status === "healthy" || source.status === "completed").length ?? 0;
  const completeness = Math.min(100, Math.max(0, Math.round(profileCompleteness)));
  return (
    <SectionCard
      className="scroll-mt-24"
      title="Settings overview"
      description="A quick read on shared data, your latest matches, refresh allowance, and profile readiness."
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" id="settings-overview">
        <OverviewCard
          eyebrow="Shared job data"
          icon={<Database className="h-5 w-5" />}
          value={freshness?.overall.status || "Checking"}
          detail={`Last refreshed ${formatDateTime(freshness?.overall.last_successful_refresh_at)}. ${healthySources} of ${freshness?.sources.length ?? 0} sources healthy.`}
        >
          <div className="mt-3 flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5" />
            {freshness?.overall.is_stale ? "Refresh may be delayed" : "Freshness checks are current"}
          </div>
        </OverviewCard>
        <OverviewCard
          eyebrow="Daily refresh allowance"
          icon={<RefreshCcw className="h-5 w-5" />}
          value={quota?.limit === null
            ? "Unlimited"
            : quota
              ? `${quota.remaining ?? 0} of ${quota.limit}`
              : "Checking"}
          detail={quota
            ? quota.limit === null
              ? `${quota.used} successful refreshes today. Failed and cancelled attempts do not count.`
              : `${quota.used} successful refreshes used. Failed and cancelled attempts do not count.`
            : "Loading your personal refresh allowance."}
        >
          <div className="mt-3 flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5" />
            Resets {formatDateTime(quota?.resets_at)}
          </div>
        </OverviewCard>
        <OverviewCard
          eyebrow="Your matches"
          icon={<Sparkles className="h-5 w-5" />}
          value={lastRun?.status || "Not run yet"}
          detail={successful
            ? `${successful.jobs_matched ?? 0} matches from the last successful refresh at ${formatDateTime(successful.published_at || successful.completed_at)}.`
            : "Refresh your matches after saving preferences to create your personal results."}
        >
          {successful ? <div className="mt-3 flex items-center gap-2 text-xs font-medium text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Last refresh completed</div> : null}
        </OverviewCard>
        <OverviewCard
          eyebrow="Profile completeness"
          icon={<UserRoundCheck className="h-5 w-5" />}
          value={`${completeness}%`}
          detail="Based on saved search preferences, skills, and match priorities."
        >
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted" aria-label={`Profile ${completeness}% complete`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={completeness}>
            <div className="h-full rounded-full bg-primary transition-all motion-reduce:transition-none" style={{ width: `${completeness}%` }} />
          </div>
        </OverviewCard>
      </div>
    </SectionCard>
  );
}

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, Play, RefreshCcw, XCircle } from "lucide-react";

import { useAccount } from "@/components/auth/account-context";
import { MetricCard } from "@/components/dashboard/metric-card";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { ConfigEditor } from "@/components/settings/config-editor";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { SectionCard } from "@/components/shared/section-card";
import {
  cancelPipelineRun,
  createPipelineRun,
  downloadExcelExport,
  getDataFreshness,
  getPipelineRun,
  getPipelineRuns
} from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import type { DataFreshness, UserPipelineRun } from "@/lib/types";

function normalizeRuns(value: Awaited<ReturnType<typeof getPipelineRuns>>) {
  return Array.isArray(value) ? value : value.items;
}

function RunStatus({ status }: { status: string }) {
  const complete = status === "completed";
  const failed = status === "failed" || status === "cancelled";
  const Icon = complete ? CheckCircle2 : failed ? XCircle : RefreshCcw;
  return <span className={`badge ${complete ? "border-emerald-200 bg-emerald-50 text-emerald-800" : failed ? "border-red-200 bg-red-50 text-red-800" : "border-cyan-200 bg-cyan-50 text-cyan-800"}`}><Icon className={`h-3.5 w-3.5 ${status === "running" ? "animate-spin" : ""}`} />{status}</span>;
}

export default function SettingsPage() {
  const user = useAccount();
  const readOnly = Boolean(user?.is_demo);
  const [freshness, setFreshness] = useState<DataFreshness | null>(null);
  const [runs, setRuns] = useState<UserPipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [message, setMessage] = useState("");

  const refreshRuns = useCallback(async () => {
    const result = await getPipelineRuns();
    setRuns(normalizeRuns(result));
  }, []);

  useEffect(() => {
    Promise.all([getDataFreshness(), getPipelineRuns()])
      .then(([nextFreshness, nextRuns]) => { setFreshness(nextFreshness); setRuns(normalizeRuns(nextRuns)); })
      .catch((requestError) => setError(requestError instanceof Error ? requestError : new Error("Settings unavailable.")))
      .finally(() => setLoading(false));
  }, []);

  const activeRun = useMemo(() => runs.find((run) => run.status === "waiting_for_global" || run.status === "queued" || run.status === "running"), [runs]);
  const lastSuccessfulRun = useMemo(() => runs.find((run) => run.status === "completed"), [runs]);

  useEffect(() => {
    if (!activeRun) return;
    const interval = window.setInterval(async () => {
      try {
        const next = await getPipelineRun(activeRun.run_uuid);
        setRuns((current) => current.map((run) => run.run_uuid === next.run_uuid ? next : run));
        if (next.status !== "waiting_for_global" && next.status !== "queued" && next.status !== "running") await refreshRuns();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError : new Error("Pipeline status unavailable."));
      }
    }, 2000);
    return () => window.clearInterval(interval);
  }, [activeRun, refreshRuns]);

  async function startPipeline() {
    setBusy(true); setError(null); setMessage("");
    try {
      const run = await createPipelineRun();
      setRuns((current) => [run, ...current]);
      setMessage(run.is_bootstrap_run ? "Your first refresh will update the shared job dataset using your search preferences before generating your personal matches." : "Your personal pipeline was queued against the latest successfully published shared job data. Shared job sources were not contacted.");
    } catch (requestError) { setError(requestError instanceof Error ? requestError : new Error("Pipeline submission failed.")); }
    finally { setBusy(false); }
  }

  async function cancel(run: UserPipelineRun) {
    setBusy(true);
    try { const next = await cancelPipelineRun(run.run_uuid); setRuns((current) => current.map((item) => item.run_uuid === next.run_uuid ? next : item)); }
    catch (requestError) { setError(requestError instanceof Error ? requestError : new Error("Cancellation failed.")); }
    finally { setBusy(false); }
  }

  async function exportExcel() {
    setBusy(true); setMessage("");
    try {
      await downloadExcelExport();
      setMessage("Your user-scoped workbook was downloaded.");
    } catch (requestError) { setError(requestError instanceof Error ? requestError : new Error("Export failed.")); }
    finally { setBusy(false); }
  }

  return (
    <AppShell>
      <PageHeader eyebrow="Settings" title="Account and personal matching" description="Review account access, shared-data freshness, personal configuration, and your user-scoped dbt refresh." />
      {loading ? <LoadingState label="Loading settings…" /> : null}
      {error ? <ErrorState error={error} title="Settings operation failed" /> : null}

      {user ? <SectionCard title="Account" description="Your application identity and current entitlement."><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><MetricCard label="Username" value={user.username} /><MetricCard label="Status" value={user.account_status} /><MetricCard label="Activated" value={formatDateTime(user.activated_at)} /><MetricCard label="Expires" value={user.expires_at ? formatDateTime(user.expires_at) : "Never"} /><MetricCard label="Remaining Days" value={user.is_demo || user.role === "admin" ? "Unlimited" : String(user.remaining_days ?? 0)} /></div>{readOnly ? <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Demo data is fixed and read-only.</p> : null}</SectionCard> : null}

      {freshness ? <SectionCard className="mt-6" title="Global shared job-data freshness" description="Platform-wide source freshness for everyone. Your personal result refresh is shown in the Personal dbt Pipeline card below."><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><MetricCard label="Shared Source Status" value={freshness.overall.status} /><MetricCard label="Shared Source Refresh" value={formatDateTime(freshness.overall.last_successful_refresh_at)} /><MetricCard label="Next Shared Refresh" value={formatDateTime(freshness.overall.next_scheduled_refresh_at)} /><MetricCard label="Shared Data As Of" value={formatDateTime(freshness.overall.data_as_of)} /></div>{freshness.overall.is_stale ? <p className="mt-4 flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="h-4 w-4" />Shared job data may be stale.</p> : null}<div className="mt-4 table-shell overflow-x-auto"><table className="data-table min-w-[700px]"><thead><tr><th>Source</th><th>Status</th><th>Shared source refresh</th><th>Records retained</th><th>Message</th></tr></thead><tbody>{freshness.sources.map((source) => <tr key={source.source_name}><td className="font-semibold">{source.source_name}</td><td>{source.status}</td><td>{formatDateTime(source.last_successful_refresh_at)}</td><td>{source.records_retained ?? 0}</td><td>{source.public_status_message || "—"}</td></tr>)}</tbody></table></div></SectionCard> : null}

      <div className="mt-6 space-y-6"><ConfigEditor type="candidate_profile" readOnly={readOnly} /><ConfigEditor type="jobs_config" readOnly={readOnly} /><ConfigEditor type="skill_taxonomy" readOnly={readOnly} /></div>

      <SectionCard className="mt-6" title="Personal dbt Pipeline" description="Your user-scoped result refresh. This scores and summarizes the existing shared job universe using your immutable configuration snapshot.">
        <div className="mb-5 grid gap-4 sm:grid-cols-3"><MetricCard label="Personal Run Status" value={runs[0]?.status || "Never run"} /><MetricCard label="Personal Results Updated" value={lastSuccessfulRun ? formatDateTime(lastSuccessfulRun.published_at || lastSuccessfulRun.completed_at) : "None"} /><MetricCard label="Personal Result Run" value={user?.last_successful_pipeline_run_uuid || "None"} /></div>
        <p className="mb-4 text-sm text-muted-foreground">{lastSuccessfulRun ? "Running your personal pipeline recalculates your matches using the latest successfully published shared job data." : "Your first refresh will update the shared job dataset using your search preferences before generating your personal matches."}</p>
        <div className="flex flex-wrap gap-3"><button className="btn btn-primary" disabled={readOnly || busy || Boolean(activeRun)} type="button" onClick={startPipeline}><Play className="h-4 w-4" />{activeRun ? "Pipeline active" : "Run Personal Pipeline"}</button><button className="btn" disabled={readOnly || busy} type="button" onClick={exportExcel}><Download className="h-4 w-4" />Export My Current Results</button></div>
        {readOnly ? <p className="mt-3 text-sm text-amber-800">Demo Pipeline and export actions are disabled.</p> : null}{message ? <p className="mt-3 text-sm font-medium text-primary">{message}</p> : null}
        <div className="mt-5 space-y-3">{runs.length ? runs.map((run) => <article key={run.run_uuid} className="rounded-md border border-border bg-background p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="font-mono text-xs text-muted-foreground">{run.run_uuid}</div><div className="mt-1 text-sm">Submitted {formatDateTime(run.submitted_at)} · {run.jobs_matched ?? 0} matched of {run.jobs_considered ?? 0} considered</div></div><div className="flex items-center gap-2"><RunStatus status={run.status} />{run.status === "queued" ? <button className="btn h-8 px-3 text-xs" disabled={busy || readOnly} type="button" onClick={() => cancel(run)}>Cancel</button> : null}</div></div>{run.public_error_message ? <p className="mt-3 text-sm text-red-800">{run.public_error_message}</p> : null}{run.events?.length ? <ol className="mt-3 space-y-1 border-l-2 border-border pl-3">{run.events.slice(-5).map((event, index) => <li key={event.event_uuid || `${event.created_at}-${index}`} className="text-sm"><span className="text-muted-foreground">{formatDateTime(event.created_at)}</span> · {event.message}</li>)}</ol> : null}</article>) : <p className="rounded-md border border-dashed border-border p-5 text-sm text-muted-foreground">No personal Pipeline runs yet.</p>}</div>
      </SectionCard>
    </AppShell>
  );
}

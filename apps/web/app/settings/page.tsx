"use client";

import { useEffect, useState } from "react";
import { Database, Download, FileSpreadsheet, Play, TestTube2 } from "lucide-react";

import { MetricCard } from "@/components/dashboard/metric-card";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { DataStatusBadge } from "@/components/shared/data-status-badge";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { SectionCard } from "@/components/shared/section-card";
import {
  exportExcel,
  getDataStatus,
  getExcelDownloadUrl,
  runDbt,
  runPipeline,
  testDbt
} from "@/lib/api";
import { formatDate, formatNullable } from "@/lib/formatters";
import type { ActionResponse, ApiError, DataStatus } from "@/lib/types";

type ActionName = "pipeline" | "dbt" | "dbtTest" | "excel";

export default function SettingsPage() {
  const [status, setStatus] = useState<DataStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [fullRefresh, setFullRefresh] = useState(false);
  const [runningAction, setRunningAction] = useState<ActionName | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<ApiError | Error | null>(null);

  async function refreshStatus() {
    setStatus(await getDataStatus());
  }

  useEffect(() => {
    refreshStatus()
      .catch((requestError) => setError(requestError as ApiError))
      .finally(() => setLoading(false));
  }, []);

  async function runAction(label: string, actionName: ActionName, action: () => Promise<ActionResponse>) {
    setRunningAction(actionName);
    setMessage(`${label} running...`);
    setError(null);
    try {
      await action();
      setMessage(`${label} completed.`);
      await refreshStatus();
    } catch (requestError) {
      setMessage("");
      setError(requestError as ApiError);
    } finally {
      setRunningAction(null);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Settings"
        title="Operational control center"
        description="Run data refreshes, rebuild dbt marts, export Excel, and inspect the active repository mode without exposing secrets to the browser."
        action={<DataStatusBadge status={status} />}
      />

      {loading ? <LoadingState label="Loading data status..." /> : null}
      {error ? <ErrorState error={error} /> : null}

      {status ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard icon={<Database className="h-5 w-5" />} label="Data Mode" value={formatNullable(status.data_mode)} />
            <MetricCard label="MotherDuck Database" value={formatNullable(status.motherduck_database || status.database)} />
            <MetricCard label="Mart Tables" value={status.mart_tables_available ? "Available" : "Pending"} />
            <MetricCard label="Excel Exists" value={status.excel_exists ? "Yes" : "No"} />
            <MetricCard label="Last Pipeline Run" value={formatDate(status.last_pipeline_run_at || status.last_pipeline_run)} />
            <MetricCard label="Last dbt Run" value={formatDate(status.last_dbt_run_at || status.last_dbt_run)} />
            <MetricCard label="Last dbt Test" value={formatDate(status.last_dbt_test_at)} />
            <MetricCard label="Latest Run Status" value={formatNullable(status.latest_run_status)} />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_0.9fr]">
            <SectionCard title="Pipeline Actions" description="These actions call FastAPI endpoints. Long runs may take a moment.">
              <div className="grid gap-3 md:grid-cols-2">
                <button
                  className="btn btn-primary justify-start"
                  disabled={Boolean(runningAction)}
                  type="button"
                  onClick={() => runAction("Pipeline", "pipeline", runPipeline)}
                >
                  <Play className="h-4 w-4" />
                  Run Pipeline
                </button>
                <button
                  className="btn justify-start"
                  disabled={Boolean(runningAction)}
                  type="button"
                  onClick={() => runAction("dbt Models", "dbt", () => runDbt(fullRefresh))}
                >
                  <Database className="h-4 w-4" />
                  Run dbt Models
                </button>
                <button
                  className="btn justify-start"
                  disabled={Boolean(runningAction)}
                  type="button"
                  onClick={() => runAction("dbt Tests", "dbtTest", testDbt)}
                >
                  <TestTube2 className="h-4 w-4" />
                  Run dbt Tests
                </button>
                <button
                  className="btn justify-start"
                  disabled={Boolean(runningAction)}
                  type="button"
                  onClick={() => runAction("Excel Export", "excel", exportExcel)}
                >
                  <FileSpreadsheet className="h-4 w-4" />
                  Export Excel
                </button>
              </div>
              <label className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  checked={fullRefresh}
                  className="h-4 w-4"
                  type="checkbox"
                  onChange={(event) => setFullRefresh(event.target.checked)}
                />
                Run dbt with full refresh
              </label>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <a
                  className="btn"
                  href={getExcelDownloadUrl()}
                  rel="noreferrer"
                  target="_blank"
                >
                  <Download className="h-4 w-4" />
                  Download Excel
                </a>
                {message ? <span className="text-sm font-medium text-primary">{message}</span> : null}
              </div>
            </SectionCard>

            <SectionCard title="Runtime Metadata">
              <dl className="grid gap-3 text-sm">
                {[
                  ["Excel Path", status.excel_path],
                  ["Excel Source", status.excel_source],
                  ["dbt Project Dir", status.dbt_project_dir],
                  ["dbt Profiles Dir", status.dbt_profiles_dir],
                  ["Local Mode Available", status.local_mode_available ? "Yes" : "No"],
                  ["MotherDuck Mode Available", status.motherduck_mode_available ? "Yes" : "No"],
                  ["Configured Sources", status.configured_sources?.join(", ")],
                  ["Job Categories", status.job_sources?.join(", ")]
                ].map(([label, value]) => (
                  <div key={label} className="rounded-md border border-border bg-background p-3">
                    <dt className="text-xs font-semibold uppercase text-muted-foreground">{label}</dt>
                    <dd className="mt-1 break-words text-foreground">{formatNullable(value)}</dd>
                  </div>
                ))}
              </dl>
            </SectionCard>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, FileSpreadsheet, Play, RefreshCcw } from "lucide-react";

import { MetricCard } from "@/components/dashboard/metric-card";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { SectionCard } from "@/components/shared/section-card";
import { PipelineQuotaCard } from "@/components/settings/pipeline-quota-card";
import { PipelineRunTimeline } from "@/components/settings/pipeline-run-timeline";
import {
  exportExcel,
  getDataStatus,
  getExcelDownloadUrl,
  getPipelineRun,
  runPipeline
} from "@/lib/api";
import { formatDateTime, formatNullable } from "@/lib/formatters";
import type { ActionResponse, ApiError, DataStatus, PipelineRunStatus } from "@/lib/types";

type ActionName = "pipeline" | "excel";

export default function SettingsPage() {
  const [status, setStatus] = useState<DataStatus | null>(null);
  const [activeRun, setActiveRun] = useState<PipelineRunStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningAction, setRunningAction] = useState<ActionName | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<ApiError | Error | null>(null);
  const activeRunId = activeRun?.run_id;
  const activeRunStatus = activeRun?.status;

  const refreshStatus = useCallback(async () => {
    const nextStatus = await getDataStatus();
    setStatus(nextStatus);
    return nextStatus;
  }, []);

  useEffect(() => {
    refreshStatus()
      .catch((requestError) => setError(requestError as ApiError))
      .finally(() => setLoading(false));
  }, [refreshStatus]);

  useEffect(() => {
    if (!activeRunId || activeRunStatus !== "running") {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const nextRun = await getPipelineRun(activeRunId);
        setActiveRun(nextRun);
        if (nextRun.quota) {
          setStatus((current) => current ? { ...current, pipeline_quota: nextRun.quota } : current);
        }
        if (nextRun.status !== "running") {
          await refreshStatus();
        }
      } catch (requestError) {
        setError(requestError as ApiError);
      }
    }, 1500);

    return () => window.clearInterval(interval);
  }, [activeRunId, activeRunStatus, refreshStatus]);

  async function startPipeline() {
    setRunningAction("pipeline");
    setMessage("");
    setError(null);
    try {
      const run = await runPipeline();
      setActiveRun(run);
      if (run.quota) {
        setStatus((current) => current ? { ...current, pipeline_quota: run.quota } : current);
      }
    } catch (requestError) {
      setError(requestError as ApiError);
    } finally {
      setRunningAction(null);
    }
  }

  async function runExcelExport(action: () => Promise<ActionResponse>) {
    setRunningAction("excel");
    setMessage("Preparing Excel export...");
    setError(null);
    try {
      await action();
      setMessage("Excel export completed.");
      await refreshStatus();
    } catch (requestError) {
      setMessage("");
      setError(requestError as ApiError);
    } finally {
      setRunningAction(null);
    }
  }

  const quota = status?.pipeline_quota;
  const quotaRemaining = quota?.remaining ?? 0;
  const pipelineRunning = activeRun?.status === "running";
  const disablePipeline = Boolean(runningAction || pipelineRunning || quotaRemaining <= 0);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Settings"
        title="Operational control center"
        description="Refresh the job intelligence pipeline, monitor progress, and export the latest workbook without exposing warehouse details."
        action={
          <div className="badge border-teal-200 bg-teal-50 text-teal-800">
            {quotaRemaining === 1 ? "1 refresh available" : `${quotaRemaining} refreshes available`}
          </div>
        }
      />

      {loading ? <LoadingState label="Loading operational status..." /> : null}
      {error ? <ErrorState error={error} title="Operation failed" /> : null}

      {status ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              icon={<RefreshCcw className="h-5 w-5" />}
              label="Refreshes Remaining"
              value={String(quotaRemaining)}
            />
            <MetricCard
              label="Last Pipeline Run"
              value={formatDateTime(status.last_pipeline_run_at || status.last_pipeline_run)}
            />
            <MetricCard
              label="Latest Run Status"
              value={formatNullable(status.latest_run_status || activeRun?.status)}
            />
            <MetricCard
              label="Excel Workbook"
              value={status.excel_exists ? "Available" : "Not ready"}
            />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
            <div className="space-y-6">
              <PipelineQuotaCard quota={quota} />

              <SectionCard
                title="Pipeline Actions"
                description="Run at most two refreshes per quota window. Refreshes reset every day at 6:00 AM ET."
              >
                <div className="grid gap-3">
                  <button
                    className="btn btn-primary justify-start"
                    disabled={disablePipeline}
                    type="button"
                    onClick={startPipeline}
                  >
                    <Play className="h-4 w-4" />
                    Run Pipeline
                  </button>
                  {quotaRemaining <= 0 ? (
                    <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                      0 refreshes available - resets at 6:00 AM ET.
                    </p>
                  ) : null}
                </div>
              </SectionCard>

              <SectionCard
                title="Excel Export"
                description="Create or download the latest workbook for offline review."
              >
                <div className="flex flex-wrap gap-3">
                  <button
                    className="btn justify-start"
                    disabled={Boolean(runningAction)}
                    type="button"
                    onClick={() => runExcelExport(exportExcel)}
                  >
                    <FileSpreadsheet className="h-4 w-4" />
                    Export Excel
                  </button>
                  <a
                    className={`btn ${status.excel_exists ? "" : "pointer-events-none opacity-60"}`}
                    href={getExcelDownloadUrl()}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <Download className="h-4 w-4" />
                    Download Excel
                  </a>
                </div>
                {message ? <p className="mt-3 text-sm font-medium text-primary">{message}</p> : null}
              </SectionCard>
            </div>

            <PipelineRunTimeline run={activeRun} />
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

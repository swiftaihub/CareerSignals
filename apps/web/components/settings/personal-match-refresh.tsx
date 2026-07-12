import Link from "next/link";
import { CheckCircle2, ChevronDown, Download, ExternalLink, Loader2, Play, XCircle } from "lucide-react";

import { SectionCard } from "@/components/shared/section-card";
import { formatDateTime, formatEasternDateTime } from "@/lib/formatters";
import { latestApplicablePipelineFailure, pipelineQuotaExhausted } from "@/lib/preferences";
import type { PipelineQuota, UserPipelineRun } from "@/lib/types";

const ACTIVE_STATES = new Set(["waiting_for_global", "queued", "running"]);

function RunStatus({ status }: { status: string }) {
  const complete = status === "completed";
  const failed = status === "failed" || status === "cancelled";
  return (
    <span className={`badge ${complete ? "border-emerald-200 bg-emerald-50 text-emerald-800" : failed ? "border-red-200 bg-red-50 text-red-800" : "border-cyan-200 bg-cyan-50 text-cyan-800"}`}>
      {complete ? <CheckCircle2 className="h-3.5 w-3.5" /> : failed ? <XCircle className="h-3.5 w-3.5" /> : <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />}
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function PersonalMatchRefresh({
  runs,
  busy,
  readOnly,
  quota,
  message,
  onStart,
  onCancel,
  onExport
}: {
  runs: UserPipelineRun[];
  busy: boolean;
  readOnly: boolean;
  quota: PipelineQuota | null;
  message?: string;
  onStart: () => void;
  onCancel: (run: UserPipelineRun) => void;
  onExport: () => void;
}) {
  const activeRun = runs.find((run) => ACTIVE_STATES.has(run.status));
  const lastAttempt = runs[0];
  const lastSuccessful = runs.find((run) => run.status === "completed");
  const lastFailure = latestApplicablePipelineFailure(runs);
  const quotaExhausted = pipelineQuotaExhausted(quota);

  return (
    <SectionCard
      className="mt-6 scroll-mt-24"
      title="Refresh My Matches"
      description="Use your latest saved preferences and skills to refresh your personalized job matches."
    >
      <div id="personal-match-refresh">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {[
            ["Current status", activeRun?.status || lastAttempt?.status || "Not run yet"],
            ["Last successful run", lastSuccessful ? formatDateTime(lastSuccessful.completed_at) : "None"],
            ["Last attempted run", lastAttempt ? formatDateTime(lastAttempt.submitted_at) : "None"],
            ["Matches updated", lastSuccessful?.jobs_matched?.toLocaleString() ?? "—"]
          ].map(([label, value]) => (
            <div className="rounded-lg border border-border bg-background p-4" key={label}>
              <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
              <div className="mt-2 text-sm font-semibold capitalize text-foreground">{value}</div>
            </div>
          ))}
        </div>

        {lastFailure?.public_error_message ? (
          <p className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900" role="alert">
            <strong>Most recent error:</strong> {lastFailure.public_error_message}
          </p>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-3">
          <button className="btn btn-primary" disabled={readOnly || busy || Boolean(activeRun) || quotaExhausted} type="button" onClick={onStart}>
            {activeRun || busy ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Play className="h-4 w-4" />}
            {activeRun ? "Refresh in progress" : busy ? "Starting refresh…" : quotaExhausted ? "Daily limit reached" : "Refresh My Matches"}
          </button>
          <Link className="btn" href="/top-matches">Review Results<ExternalLink className="h-4 w-4" /></Link>
          <button className="btn" disabled={readOnly || busy} type="button" onClick={onExport}><Download className="h-4 w-4" />Export Current Results</button>
        </div>
        {readOnly ? <p className="mt-3 text-sm text-amber-800">Demo refresh and export actions are read-only.</p> : null}
        {quotaExhausted ? <p className="mt-3 text-sm text-amber-800">Your successful-refresh allowance resets {formatEasternDateTime(quota?.resets_at)}. Failed and cancelled attempts do not count.</p> : null}
        {message ? <p className="mt-3 text-sm font-medium text-primary" aria-live="polite">{message}</p> : null}

        <details className="group mt-6 border-t border-border pt-5">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-md py-2 text-sm font-semibold text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary">
            Recent refresh history
            <ChevronDown className="h-4 w-4 text-muted-foreground transition group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
          </summary>
          <div className="mt-3 space-y-3">
            {runs.length ? runs.slice(0, 8).map((run) => (
              <article className="rounded-lg border border-border bg-background p-4" key={run.run_uuid}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold">Submitted {formatDateTime(run.submitted_at)}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {run.jobs_matched ?? 0} matched of {run.jobs_considered ?? 0} considered · {run.is_bootstrap_run ? "First refresh" : "Personal refresh"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <RunStatus status={run.status} />
                    {(run.status === "queued" || run.status === "waiting_for_global") ? (
                      <button className="btn h-8 px-3 text-xs" disabled={busy || readOnly} type="button" onClick={() => onCancel(run)}>Cancel</button>
                    ) : null}
                  </div>
                </div>
                {run.public_error_message ? <p className="mt-3 text-sm text-red-800">{run.public_error_message}</p> : null}
                {run.events?.length ? (
                  <ol className="mt-3 space-y-1 border-l-2 border-border pl-3">
                    {run.events.slice(-3).map((event, index) => (
                      <li className="text-xs text-muted-foreground" key={event.event_uuid || `${event.created_at}-${index}`}>
                        {formatDateTime(event.created_at)} · {event.message}
                      </li>
                    ))}
                  </ol>
                ) : null}
              </article>
            )) : <p className="rounded-lg border border-dashed border-border p-5 text-sm text-muted-foreground">No personal match refreshes yet.</p>}
          </div>
        </details>
      </div>
    </SectionCard>
  );
}

import { AlertTriangle, CheckCircle2, Clock3, Loader2 } from "lucide-react";

import type { PipelineRunMessage, PipelineRunStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

function formatTime(value?: string | null) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit"
  }).format(date);
}

function statusTone(status?: string) {
  if (status === "completed") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (status === "failed") {
    return "border-red-200 bg-red-50 text-red-800";
  }
  return "border-teal-200 bg-teal-50 text-teal-800";
}

function messageTone(level?: string) {
  if (level === "error") {
    return "border-red-200 bg-red-50 text-red-900";
  }
  if (level === "warning") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }
  return "border-border bg-background text-foreground";
}

function SummaryValue({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold text-foreground">{String(value)}</div>
    </div>
  );
}

function TimelineMessage({ message }: { message: PipelineRunMessage }) {
  return (
    <li className={cn("rounded-md border p-3 text-sm", messageTone(message.level))}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{message.message}</span>
        <span className="text-xs text-muted-foreground">{formatTime(message.timestamp)}</span>
      </div>
    </li>
  );
}

export function PipelineRunTimeline({ run }: { run?: PipelineRunStatus | null }) {
  const latestMessage = run?.messages?.at(-1)?.message;
  const isRunning = run?.status === "running";
  const isCompleted = run?.status === "completed";
  const isFailed = run?.status === "failed";

  return (
    <section className="rounded-lg border border-border bg-card p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground">
            Live Pipeline Progress
          </div>
          <h2 className="mt-2 text-lg font-semibold text-foreground">
            {run ? latestMessage || "Pipeline run initialized" : "No active run"}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {run
              ? `Run ${run.run_id} started ${formatTime(run.started_at)}`
              : "Start a refresh to see backend progress messages here."}
          </p>
        </div>
        <div className={cn("badge", statusTone(run?.status))}>
          {isRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          {isCompleted ? <CheckCircle2 className="h-3.5 w-3.5" /> : null}
          {isFailed ? <AlertTriangle className="h-3.5 w-3.5" /> : null}
          {!run ? <Clock3 className="h-3.5 w-3.5" /> : null}
          {run?.status || "idle"}
        </div>
      </div>

      {run?.messages?.length ? (
        <ol className="mt-5 max-h-80 space-y-2 overflow-y-auto pr-1">
          {run.messages.map((message, index) => (
            <TimelineMessage key={`${message.timestamp}-${index}`} message={message} />
          ))}
        </ol>
      ) : (
        <div className="mt-5 rounded-md border border-dashed border-border bg-background p-5 text-sm text-muted-foreground">
          Backend messages will appear as the run advances.
        </div>
      )}

      {run?.summary ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryValue label="Jobs Considered" value={run.summary.jobs_considered} />
          <SummaryValue label="Jobs Matched" value={run.summary.jobs_matched} />
          <SummaryValue label="Top Matches" value={run.summary.top_matches} />
        </div>
      ) : null}
    </section>
  );
}

"use client";

import { useEffect, useState } from "react";
import { RefreshCcw } from "lucide-react";

import { createAdminConnectorRun, getAdminConnectorRuns } from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import type { AdminConnectorRun } from "@/lib/types";

export function GlobalRefreshControl() {
  const [runs, setRuns] = useState<AdminConnectorRun[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    const result = await getAdminConnectorRuns();
    setRuns(result.items || []);
  }

  useEffect(() => {
    refresh().catch(() => setError("Global refresh status is unavailable."));
  }, []);

  async function enqueue() {
    setBusy(true); setError(""); setMessage("");
    try {
      const run = await createAdminConnectorRun();
      setMessage(`Manual global refresh queued: ${run.connector_run_uuid}`);
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Manual global refresh failed.");
    } finally {
      setBusy(false);
    }
  }

  const latest = runs[0];
  return (
    <section className="mt-6 rounded-lg border border-border bg-card p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Global Refresh</h2>
          <p className="mt-1 text-sm text-muted-foreground">Shared connector acquisition and shared dbt publication.</p>
        </div>
        <button className="btn btn-primary" disabled={busy} type="button" onClick={enqueue}>
          <RefreshCcw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />Manual Global Refresh
        </button>
      </div>
      {message ? <p className="mt-3 text-sm font-medium text-primary">{message}</p> : null}
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <div><div className="text-xs uppercase text-muted-foreground">Last Status</div><div className="mt-1 font-semibold">{latest?.status || "None"}</div></div>
        <div><div className="text-xs uppercase text-muted-foreground">Trigger</div><div className="mt-1 font-semibold">{latest?.trigger_type || "None"}</div></div>
        <div><div className="text-xs uppercase text-muted-foreground">Completed</div><div className="mt-1 font-semibold">{formatDateTime(latest?.completed_at)}</div></div>
        <div><div className="text-xs uppercase text-muted-foreground">Included Users</div><div className="mt-1 font-semibold">{latest?.included_user_count ?? 0}</div></div>
        <div><div className="text-xs uppercase text-muted-foreground">Unique Queries</div><div className="mt-1 font-semibold">{latest?.acquisition_query_count ?? 0}</div></div>
      </div>
    </section>
  );
}

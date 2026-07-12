import { History, RotateCcw } from "lucide-react";

import { formatDateTime } from "@/lib/formatters";
import type { PreferencesRevision, PreferencesRevisionEntry } from "@/lib/types";

export function RevisionHistory({
  current,
  history,
  busy,
  readOnly,
  onRestore
}: {
  current: PreferencesRevision;
  history: PreferencesRevisionEntry[];
  busy: boolean;
  readOnly: boolean;
  onRestore: (revision: PreferencesRevisionEntry) => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-background p-4">
      <div className="flex items-center gap-2"><History className="h-4 w-4 text-primary" /><h3 className="text-sm font-semibold">Configuration history</h3></div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">Restores apply a complete preference bundle, keeping generated configurations coherent.</p>
      <div className="mt-3 space-y-2">
        {history.length ? history.map((entry, index) => {
          const identifier = entry.revision ?? entry.bundle_uuid;
          const active = Boolean(entry.bundle_uuid && entry.bundle_uuid === current.bundle_uuid);
          return (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card p-3" key={entry.bundle_uuid || `${entry.revision}-${index}`}>
              <div>
                <div className="text-sm font-semibold">{entry.revision !== null && entry.revision !== undefined ? `Revision ${entry.revision}` : `Bundle ${entry.bundle_uuid?.slice(0, 8) || "Unknown"}`}{active ? " · Active" : ""}</div>
                <div className="mt-1 text-xs text-muted-foreground">{formatDateTime(entry.created_at)}{entry.generator_version ? ` · Generator ${entry.generator_version}` : ""}</div>
              </div>
              <button className="btn h-9 px-3 text-xs" disabled={readOnly || busy || active || identifier === null || identifier === undefined} type="button" onClick={() => onRestore(entry)}><RotateCcw className="h-3.5 w-3.5" />Restore</button>
            </div>
          );
        }) : <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">No prior bundle revisions are available.</p>}
      </div>
    </div>
  );
}

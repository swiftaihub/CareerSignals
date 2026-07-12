import { ChevronDown, Eye, RotateCcw, Settings2 } from "lucide-react";

import { GeneratedPreview } from "@/components/settings/generated-preview";
import { RevisionHistory } from "@/components/settings/revision-history";
import type {
  PreferencesGeneratedPreview,
  PreferencesRevision,
  PreferencesRevisionEntry
} from "@/lib/types";

export function AdvancedHistory({
  preview,
  revision,
  history,
  warnings,
  busy,
  readOnly,
  onPreview,
  onRestore,
  onReset
}: {
  preview: PreferencesGeneratedPreview;
  revision: PreferencesRevision;
  history: PreferencesRevisionEntry[];
  warnings: string[];
  busy: boolean;
  readOnly: boolean;
  onPreview: () => void;
  onRestore: (revision: PreferencesRevisionEntry) => void;
  onReset: () => void;
}) {
  return (
    <section className="mt-6 scroll-mt-24 rounded-lg border border-border bg-card shadow-soft" id="advanced-history">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset">
          <div className="flex items-start gap-3">
            <span className="rounded-lg bg-muted p-2 text-primary"><Settings2 className="h-5 w-5" /></span>
            <div><h2 className="text-base font-semibold">Advanced & History</h2><p className="mt-1 text-sm text-muted-foreground">Review generated data, the active bundle revision, warnings, and coherent restore points.</p></div>
          </div>
          <ChevronDown className="h-5 w-5 shrink-0 text-muted-foreground transition group-open:rotate-180 motion-reduce:transition-none" />
        </summary>
        <div className="border-t border-border p-5">
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-background/70 p-4">
            <div>
              <div className="text-xs font-semibold uppercase text-muted-foreground">Active configuration bundle</div>
              <div className="mt-1 text-sm font-semibold">{revision.revision !== null && revision.revision !== undefined ? `Revision ${revision.revision}` : revision.bundle_uuid?.slice(0, 12) || "Not yet saved"}</div>
              <div className="mt-1 text-xs text-muted-foreground">Generator {revision.generator_version || "default"}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn" disabled={busy} type="button" onClick={onPreview}><Eye className="h-4 w-4" />{busy ? "Working…" : "Preview Generated Data"}</button>
              <button className="btn" disabled={busy || readOnly} type="button" onClick={onReset}><RotateCcw className="h-4 w-4" />Reset to Defaults</button>
            </div>
          </div>
          <div className="mt-5"><GeneratedPreview preview={preview} warnings={warnings} /></div>
          <div className="mt-5"><RevisionHistory busy={busy} current={revision} history={history} readOnly={readOnly} onRestore={onRestore} /></div>
        </div>
      </details>
    </section>
  );
}

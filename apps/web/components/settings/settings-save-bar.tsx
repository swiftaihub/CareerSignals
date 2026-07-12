import { AlertCircle, Check, RotateCcw, Save } from "lucide-react";

export function SettingsSaveBar({
  dirty,
  saving,
  readOnly,
  errors,
  onDiscard,
  onSave
}: {
  dirty: boolean;
  saving: boolean;
  readOnly: boolean;
  errors: string[];
  onDiscard: () => void;
  onSave: () => void;
}) {
  if (!dirty) return null;
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 p-3 shadow-[0_-12px_32px_rgba(15,23,42,0.12)] backdrop-blur lg:left-64" aria-live="polite">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className={`rounded-full p-2 ${errors.length ? "bg-amber-100 text-amber-800" : "bg-teal-100 text-teal-800"}`}>{errors.length ? <AlertCircle className="h-4 w-4" /> : <Check className="h-4 w-4" />}</span>
          <div className="min-w-0"><div className="text-sm font-semibold">Unsaved preference changes</div><div className="truncate text-xs text-muted-foreground">{errors[0] || "Your next match refresh will use these settings after you save."}</div></div>
        </div>
        <div className="flex gap-2">
          <button className="btn" disabled={saving} type="button" onClick={onDiscard}><RotateCcw className="h-4 w-4" />Discard</button>
          <button className="btn btn-primary" disabled={saving || readOnly || Boolean(errors.length)} type="button" onClick={onSave}><Save className="h-4 w-4" />{saving ? "Saving…" : "Save Preferences"}</button>
        </div>
      </div>
    </div>
  );
}

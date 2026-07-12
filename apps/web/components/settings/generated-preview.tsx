import { Search, Sparkles } from "lucide-react";

import type { PreferencesGeneratedPreview } from "@/lib/types";

export function GeneratedPreview({
  preview,
  warnings
}: {
  preview: PreferencesGeneratedPreview;
  warnings: string[];
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <div className="rounded-xl border border-border bg-background p-4">
        <div className="flex items-center gap-2"><Search className="h-4 w-4 text-primary" /><h3 className="text-sm font-semibold">Generated search titles</h3></div>
        <div className="mt-3 space-y-3">
          {preview.search_titles.length ? preview.search_titles.map((item) => (
            <div className="rounded-lg border border-border bg-card p-3" key={item.title}>
              <div className="text-sm font-semibold">{item.title}</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.variations.map((variation) => <span className="badge border-border bg-background font-normal" key={variation}>{variation}</span>)}
              </div>
            </div>
          )) : <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">Preview your preferences to see generated title variations.</p>}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-background p-4">
        <div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary" /><h3 className="text-sm font-semibold">Generated skill aliases</h3></div>
        <div className="mt-3 space-y-3">
          {preview.skill_aliases.length ? preview.skill_aliases.map((item) => (
            <div className="rounded-lg border border-border bg-card p-3" key={item.canonical}>
              <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm font-semibold">{item.canonical}</span>{item.confidence !== null && item.confidence !== undefined ? <span className="text-xs text-muted-foreground">{Math.round(item.confidence * (item.confidence <= 1 ? 100 : 1))}% confidence</span> : null}</div>
              {item.category ? <div className="mt-1 text-xs text-muted-foreground">{item.category}</div> : null}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.aliases.map((alias) => <span className="badge border-border bg-background font-normal" key={alias}>{alias}</span>)}
              </div>
            </div>
          )) : <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">Preview your preferences to see normalized skill aliases.</p>}
        </div>
      </div>

      {warnings.length ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950 xl:col-span-2">
          <h3 className="font-semibold">Validation and migration notes</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
        </div>
      ) : null}
    </div>
  );
}

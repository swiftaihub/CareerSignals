"use client";

import { useEffect, useMemo, useState } from "react";
import { History, RotateCcw, Save } from "lucide-react";

import {
  getConfig,
  getConfigVersions,
  resetConfig,
  resetConfigField,
  restoreConfigVersion,
  saveConfig
} from "@/lib/api-client";
import type { ConfigDocument, ConfigType, ConfigVersion } from "@/lib/types";

const labels: Record<ConfigType, string> = {
  candidate_profile: "Candidate Profile",
  jobs_config: "Job Preferences",
  skill_taxonomy: "Skill Taxonomy"
};

const descriptions: Record<ConfigType, string> = {
  candidate_profile: "Skills and experience used by personal scoring models.",
  jobs_config: "Job data is refreshed automatically by CareerSignals. These preferences filter, categorize, and score existing jobs; saving them does not call external job APIs.",
  skill_taxonomy: "Your personal skill aliases and matching vocabulary."
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function flatten(value: unknown, prefix = ""): Array<{ path: string; value: unknown }> {
  if (isRecord(value) && Object.keys(value).length) {
    return Object.entries(value).flatMap(([key, child]) => flatten(child, prefix ? `${prefix}.${key}` : key));
  }
  return prefix ? [{ path: prefix, value }] : [];
}

function getAtPath(source: Record<string, unknown>, path: string): unknown {
  return path.split(".").reduce<unknown>((value, key) => isRecord(value) ? value[key] : undefined, source);
}

function setAtPath(source: Record<string, unknown>, path: string, value: unknown) {
  const clone = structuredClone(source);
  const parts = path.split(".");
  let cursor = clone;
  parts.forEach((part, index) => {
    if (index === parts.length - 1) cursor[part] = value;
    else {
      if (!isRecord(cursor[part])) cursor[part] = {};
      cursor = cursor[part] as Record<string, unknown>;
    }
  });
  return clone;
}

function humanize(path: string) {
  return path.split(".").at(-1)?.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) || path;
}

function formatValue(value: unknown) {
  if (value === undefined) return "Not set";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function FieldEditor({
  path,
  value,
  defaultValue,
  overridden,
  disabled,
  onChange,
  onReset
}: {
  path: string;
  value: unknown;
  defaultValue: unknown;
  overridden: boolean;
  disabled: boolean;
  onChange: (value: unknown) => void;
  onReset: () => void;
}) {
  const [text, setText] = useState(formatValue(value));
  const [localError, setLocalError] = useState("");
  useEffect(() => setText(formatValue(value)), [value]);

  function commit(next = text) {
    try {
      let parsed: unknown = next;
      if (typeof value === "number") parsed = Number(next);
      else if (typeof value === "boolean") parsed = next === "true";
      else if (Array.isArray(value) || isRecord(value) || value === null) parsed = JSON.parse(next);
      onChange(parsed);
      setLocalError("");
    } catch {
      setLocalError("Enter valid JSON for this value.");
    }
  }

  return (
    <div className="rounded-md border border-border bg-background p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <label className="text-sm font-semibold" htmlFor={`${path}-input`}>{humanize(path)}</label>
          <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">{path}</div>
        </div>
        <span className={`badge ${overridden ? "border-cyan-200 bg-cyan-50 text-cyan-800" : "border-neutral-200 bg-neutral-100 text-neutral-700"}`}>
          {overridden ? "Overridden" : "Using default"}
        </span>
      </div>
      {typeof value === "boolean" ? (
        <select id={`${path}-input`} className="select mt-3" disabled={disabled} value={String(value)} onChange={(event) => { setText(event.target.value); commit(event.target.value); }}>
          <option value="true">Yes</option><option value="false">No</option>
        </select>
      ) : Array.isArray(value) || isRecord(value) || value === null ? (
        <textarea id={`${path}-input`} className="textarea mt-3 min-h-24 font-mono text-xs" disabled={disabled} value={text} onBlur={() => commit()} onChange={(event) => setText(event.target.value)} />
      ) : (
        <input id={`${path}-input`} className="input mt-3" disabled={disabled} type={typeof value === "number" ? "number" : "text"} value={text} onBlur={() => commit()} onChange={(event) => setText(event.target.value)} />
      )}
      {localError ? <p className="mt-1 text-xs text-red-700">{localError}</p> : null}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>Default value: <code>{formatValue(defaultValue)}</code></span>
        {overridden ? <button className="font-semibold text-primary hover:underline" disabled={disabled} type="button" onClick={onReset}>Reset to default</button> : null}
      </div>
    </div>
  );
}

export function ConfigEditor({ type, readOnly }: { type: ConfigType; readOnly: boolean }) {
  const [document, setDocument] = useState<ConfigDocument | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [versions, setVersions] = useState<ConfigVersion[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    setBusy(true);
    getConfig(type)
      .then((value) => { setDocument(value); setDraft(value.override_config || {}); })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Configuration unavailable."))
      .finally(() => setBusy(false));
  }, [type]);

  const fields = useMemo(() => document ? flatten(document.effective_config) : [], [document]);

  async function perform(action: () => Promise<ConfigDocument>, success: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      const next = await action();
      setDocument(next); setDraft(next.override_config || {}); setMessage(success);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The configuration change failed.");
    } finally { setBusy(false); }
  }

  async function loadHistory() {
    setShowHistory((current) => !current);
    if (!versions.length) {
      try {
        const result = await getConfigVersions(type);
        setVersions(Array.isArray(result) ? result : []);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Version history unavailable.");
      }
    }
  }

  if (!document) return <div className="rounded-md border border-dashed border-border p-5 text-sm text-muted-foreground">{busy ? `Loading ${labels[type]}…` : error || "Configuration unavailable."}</div>;

  return (
    <section className="rounded-lg border border-border bg-card p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><h3 className="text-lg font-semibold">{labels[type]}</h3><p className="mt-1 max-w-3xl text-sm text-muted-foreground">{descriptions[type]} Revision {document.revision}; effective values merge repository defaults with your overrides.</p></div>
        <div className="flex flex-wrap gap-2">
          <button className="btn" type="button" onClick={loadHistory}><History className="h-4 w-4" />History</button>
          <button className="btn" disabled={readOnly || busy} type="button" onClick={() => perform(() => resetConfig(type), "All fields now use repository defaults.")}><RotateCcw className="h-4 w-4" />Reset all</button>
          <button className="btn btn-primary" disabled={readOnly || busy} type="button" onClick={() => perform(() => saveConfig(type, draft), "Configuration saved as a new revision.")}><Save className="h-4 w-4" />Save</button>
        </div>
      </div>
      {readOnly ? <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Demo data is fixed and read-only.</p> : null}
      {error ? <p className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900">{error}</p> : null}
      {message ? <p className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{message}</p> : null}
      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {fields.map(({ path, value }) => {
          const overrideValue = getAtPath(draft, path);
          const effectiveValue = overrideValue === undefined ? value : overrideValue;
          const overridden = document.field_sources[path] === "override" || overrideValue !== undefined;
          return <FieldEditor key={path} path={path} value={effectiveValue} defaultValue={getAtPath(document.default_config, path)} overridden={overridden} disabled={readOnly || busy} onChange={(next) => setDraft((current) => setAtPath(current, path, next))} onReset={() => perform(() => resetConfigField(type, path), `${humanize(path)} reset to default.`)} />;
        })}
      </div>
      {showHistory ? (
        <div className="mt-5 border-t border-border pt-4"><h4 className="text-sm font-semibold">Revision history</h4><div className="mt-3 space-y-2">{versions.length ? versions.map((version) => <div key={version.revision} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3 text-sm"><span>Revision {version.revision} · {new Date(version.created_at).toLocaleString()}</span><button className="btn h-8 px-3 text-xs" disabled={readOnly || busy || version.revision === document.revision} type="button" onClick={() => perform(() => restoreConfigVersion(type, version.revision), `Revision ${version.revision} restored as a new revision.`)}>Restore</button></div>) : <p className="text-sm text-muted-foreground">No prior revisions.</p>}</div></div>
      ) : null}
    </section>
  );
}

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAccount } from "@/components/auth/account-context";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { AdvancedHistory } from "@/components/settings/advanced-history";
import { MatchPriorityRadar } from "@/components/settings/match-priority-radar";
import { PersonalMatchRefresh } from "@/components/settings/personal-match-refresh";
import { SearchPreferencesForm } from "@/components/settings/search-preferences-form";
import { SettingsOverview } from "@/components/settings/settings-overview";
import { SettingsSaveBar } from "@/components/settings/settings-save-bar";
import { SharedDataFreshness } from "@/components/settings/shared-data-freshness";
import { SkillsEditor } from "@/components/settings/skills-editor";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import {
  ApiClientError,
  cancelPipelineRun,
  createPipelineRun,
  downloadExcelExport,
  getDataFreshness,
  getPipelineRun,
  getPipelineQuota,
  getPipelineRuns,
  getPreferences,
  getPreferencesOptions,
  previewPreferences,
  resetPreferences,
  restorePreferencesRevision,
  savePreferences
} from "@/lib/api-client";
import {
  EMPTY_PREFERENCES_OPTIONS,
  preferencesAreDirty,
  shouldWarnOnNavigation,
  validatePreferences
} from "@/lib/preferences";
import type {
  DataFreshness,
  PipelineQuota,
  PreferencesDocument,
  PreferenceDynamicOptionKind,
  PreferenceOption,
  PreferencesOptions,
  PreferencesRevisionEntry,
  UserPipelineRun
} from "@/lib/types";

function normalizeRuns(value: Awaited<ReturnType<typeof getPipelineRuns>>) {
  return Array.isArray(value) ? value : value.items;
}

const ACTIVE_RUN_STATES = new Set(["waiting_for_global", "queued", "running"]);

export default function SettingsPage() {
  const user = useAccount();
  const readOnly = Boolean(user?.is_demo);
  const [preferences, setPreferences] = useState<PreferencesDocument | null>(null);
  const [baseline, setBaseline] = useState<PreferencesDocument | null>(null);
  const [options, setOptions] = useState<PreferencesOptions>(EMPTY_PREFERENCES_OPTIONS);
  const [freshness, setFreshness] = useState<DataFreshness | null>(null);
  const [runs, setRuns] = useState<UserPipelineRun[]>([]);
  const [quota, setQuota] = useState<PipelineQuota | null>(null);
  const [loading, setLoading] = useState(true);
  const [preferenceBusy, setPreferenceBusy] = useState(false);
  const [pipelineBusy, setPipelineBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState("");
  const [pipelineMessage, setPipelineMessage] = useState("");

  const refreshRuns = useCallback(async () => {
    const [result, nextQuota] = await Promise.all([getPipelineRuns(), getPipelineQuota()]);
    setRuns(normalizeRuns(result));
    setQuota(nextQuota);
  }, []);

  const loadDynamicOptions = useCallback(async (
    kind: PreferenceDynamicOptionKind,
    query: string
  ): Promise<PreferenceOption[]> => {
    const result = await getPreferencesOptions({ kind, q: query, limit: 25 });
    return result[kind];
  }, []);

  useEffect(() => {
    Promise.allSettled([getPreferences(), getPreferencesOptions(), getDataFreshness(), getPipelineRuns(), getPipelineQuota()])
      .then(([preferencesResult, optionsResult, freshnessResult, runsResult, quotaResult]) => {
        if (preferencesResult.status === "rejected") throw preferencesResult.reason;
        setPreferences(preferencesResult.value);
        setBaseline(structuredClone(preferencesResult.value));
        if (optionsResult.status === "fulfilled") setOptions(optionsResult.value);
        if (freshnessResult.status === "fulfilled") setFreshness(freshnessResult.value);
        if (runsResult.status === "fulfilled") setRuns(normalizeRuns(runsResult.value));
        if (quotaResult.status === "fulfilled") setQuota(quotaResult.value);
        const unavailable = [
          optionsResult.status === "rejected" ? "suggestions" : "",
          freshnessResult.status === "rejected" ? "shared-data status" : "",
          runsResult.status === "rejected" ? "refresh history" : "",
          quotaResult.status === "rejected" ? "refresh allowance" : ""
        ].filter(Boolean);
        if (unavailable.length) {
          setNotice(`Some supporting data is temporarily unavailable: ${unavailable.join(", ")}. You can still review your saved preferences.`);
        }
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError : new Error("Settings are unavailable.")))
      .finally(() => setLoading(false));
  }, []);

  const activeRun = useMemo(
    () => runs.find((run) => ACTIVE_RUN_STATES.has(run.status)),
    [runs]
  );

  useEffect(() => {
    if (!activeRun) return;
    const interval = window.setInterval(async () => {
      try {
        const next = await getPipelineRun(activeRun.run_uuid);
        setRuns((current) => current.map((run) => run.run_uuid === next.run_uuid ? next : run));
        if (!ACTIVE_RUN_STATES.has(next.status)) await refreshRuns();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError : new Error("Match refresh status is unavailable."));
      }
    }, 2000);
    return () => window.clearInterval(interval);
  }, [activeRun, refreshRuns]);

  const dirty = Boolean(preferences && baseline && preferencesAreDirty(baseline, preferences));
  const validationErrors = preferences ? validatePreferences(preferences) : [];

  useEffect(() => {
    const warn = shouldWarnOnNavigation(dirty, preferenceBusy);
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!warn) return;
      event.preventDefault();
      event.returnValue = "";
    }
    function handleLinkClick(event: MouseEvent) {
      if (!warn || event.defaultPrevented) return;
      const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!target || target.getAttribute("target") === "_blank") return;
      const destination = target.getAttribute("href");
      if (!destination || destination.startsWith("#")) return;
      if (!window.confirm("You have unsaved preference changes. Leave without saving?")) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    document.addEventListener("click", handleLinkClick, true);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      document.removeEventListener("click", handleLinkClick, true);
    };
  }, [dirty, preferenceBusy]);

  async function startPipeline() {
    setPipelineBusy(true);
    setError(null);
    setPipelineMessage("");
    try {
      const run = await createPipelineRun();
      setRuns((current) => [run, ...current.filter((item) => item.run_uuid !== run.run_uuid)]);
      setPipelineMessage(run.is_bootstrap_run
        ? "Your first refresh will update shared job data before creating personal matches."
        : "Your match refresh was queued against the latest published shared job data.");
    } catch (requestError) {
      if (requestError instanceof ApiClientError && requestError.errorCode === "PIPELINE_DAILY_LIMIT_REACHED") {
        setPipelineMessage("Your successful-refresh allowance is used for today. Failed and cancelled attempts do not count.");
        try {
          setQuota(await getPipelineQuota());
        } catch {
          // Preserve the actionable quota message when the supporting refresh fails.
        }
      } else {
        setError(requestError instanceof Error ? requestError : new Error("Match refresh submission failed."));
      }
    } finally {
      setPipelineBusy(false);
    }
  }

  async function cancelRun(run: UserPipelineRun) {
    setPipelineBusy(true);
    try {
      const next = await cancelPipelineRun(run.run_uuid);
      setRuns((current) => current.map((item) => item.run_uuid === next.run_uuid ? next : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("Cancellation failed."));
    } finally {
      setPipelineBusy(false);
    }
  }

  async function exportExcel() {
    setPipelineBusy(true);
    setPipelineMessage("");
    try {
      await downloadExcelExport();
      setPipelineMessage("Your current user-scoped matches were exported.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("Export failed."));
    } finally {
      setPipelineBusy(false);
    }
  }

  async function generatePreview() {
    if (!preferences) return;
    setPreferenceBusy(true);
    setError(null);
    setNotice("");
    try {
      const preview = await previewPreferences(preferences);
      setPreferences((current) => current ? {
        ...current,
        generated_preview: preview.generated_preview,
        warnings: preview.warnings,
        profile_completeness: preview.profile_completeness ?? current.profile_completeness
      } : current);
      setNotice("Generated titles and skill aliases are ready to review in Advanced & History.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("Preference preview failed."));
    } finally {
      setPreferenceBusy(false);
    }
  }

  async function save() {
    if (!preferences || validationErrors.length) return;
    setPreferenceBusy(true);
    setError(null);
    setNotice("");
    try {
      const saved = await savePreferences(preferences);
      setPreferences(saved);
      setBaseline(structuredClone(saved));
      setNotice("Preferences saved. Your next match refresh will use this configuration bundle.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("Preferences could not be saved."));
    } finally {
      setPreferenceBusy(false);
    }
  }

  function discard() {
    if (!baseline) return;
    setPreferences(structuredClone(baseline));
    setNotice("Unsaved changes were discarded.");
  }

  async function restoreRevision(revision: PreferencesRevisionEntry) {
    if (dirty && !window.confirm("Restoring a revision will replace your unsaved changes. Continue?")) return;
    const identifier = revision.revision ?? revision.bundle_uuid;
    if (identifier === null || identifier === undefined) return;
    setPreferenceBusy(true);
    setError(null);
    try {
      const restored = await restorePreferencesRevision(identifier);
      setPreferences(restored);
      setBaseline(structuredClone(restored));
      setNotice("The complete preference bundle was restored as the active revision.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("Revision restore failed."));
    } finally {
      setPreferenceBusy(false);
    }
  }

  async function resetToDefaults() {
    if (!window.confirm("Reset all preferences to CareerSignals defaults? This creates a new coherent revision.")) return;
    setPreferenceBusy(true);
    setError(null);
    try {
      const reset = await resetPreferences();
      setPreferences(reset);
      setBaseline(structuredClone(reset));
      setNotice("Preferences were reset to defaults.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("Reset failed."));
    } finally {
      setPreferenceBusy(false);
    }
  }

  if (loading) {
    return <AppShell><PageHeader eyebrow="Settings" title="Personalize CareerSignals" description="Loading your saved preferences and match status." /><LoadingState label="Loading settings…" /></AppShell>;
  }

  if (!preferences) {
    return <AppShell><PageHeader eyebrow="Settings" title="Personalize CareerSignals" /><ErrorState error={error} title="Settings unavailable" /></AppShell>;
  }

  return (
    <AppShell>
      <div className="pb-24">
        <PageHeader
          eyebrow="Settings"
          title="Personalize CareerSignals"
          description="Set the opportunities, expertise, and ranking priorities that power your personal matches. CareerSignals handles the underlying configuration."
        />
        {readOnly ? <p className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Demo preferences and pipeline actions are read-only.</p> : null}
        {error ? <div className="mb-5"><ErrorState error={error} title="Settings operation failed" /></div> : null}
        {notice ? <p className={`mb-5 rounded-lg border p-3 text-sm font-medium ${notice.includes("unavailable") ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`} aria-live="polite">{notice}</p> : null}

        <SettingsOverview freshness={freshness} profileCompleteness={preferences.profile_completeness} quota={quota} runs={runs} />
        <SharedDataFreshness freshness={freshness} />
        <PersonalMatchRefresh
          busy={pipelineBusy}
          message={pipelineMessage}
          quota={quota}
          readOnly={readOnly}
          runs={runs}
          onCancel={cancelRun}
          onExport={exportExcel}
          onStart={startPipeline}
        />
        <SearchPreferencesForm
          disabled={readOnly || preferenceBusy}
          errors={validationErrors}
          options={options}
          loadOptions={loadDynamicOptions}
          value={preferences.search_preferences}
          onChange={(searchPreferences) => setPreferences((current) => current ? { ...current, search_preferences: searchPreferences } : current)}
        />
        <SkillsEditor
          categories={preferences.skill_categories}
          disabled={readOnly || preferenceBusy}
          skills={preferences.skills}
          onCategoriesChange={(skillCategories) => setPreferences((current) => current ? { ...current, skill_categories: skillCategories } : current)}
          onSkillsChange={(skills) => setPreferences((current) => current ? { ...current, skills } : current)}
        />
        <MatchPriorityRadar
          disabled={readOnly || preferenceBusy}
          value={preferences.match_priorities}
          onChange={(matchPriorities) => setPreferences((current) => current ? { ...current, match_priorities: matchPriorities } : current)}
        />
        <AdvancedHistory
          busy={preferenceBusy}
          history={preferences.revision_history}
          preview={preferences.generated_preview}
          readOnly={readOnly}
          revision={preferences.revision}
          warnings={preferences.warnings}
          onPreview={generatePreview}
          onReset={resetToDefaults}
          onRestore={restoreRevision}
        />
      </div>
      <SettingsSaveBar
        dirty={dirty}
        errors={validationErrors}
        readOnly={readOnly}
        saving={preferenceBusy}
        onDiscard={discard}
        onSave={save}
      />
    </AppShell>
  );
}

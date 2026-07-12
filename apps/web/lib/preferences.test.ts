import { describe, expect, it } from "vitest";

import {
  MATCH_PRIORITY_KEYS,
  MATCH_PRIORITY_PRESETS,
  SETTINGS_SECTION_ORDER,
  addTagValue,
  createEmptyPreferences,
  latestApplicablePipelineFailure,
  mergePreferenceOptions,
  normalizeMatchPriorities,
  preferencesAreDirty,
  redistributeMatchPriority,
  searchableOptions,
  shouldWarnOnNavigation,
  totalMatchPriorities
} from "./preferences";

describe("settings structure", () => {
  it("keeps the task-oriented sections in product order", () => {
    expect(SETTINGS_SECTION_ORDER).toEqual([
      "settings-overview",
      "shared-data-freshness",
      "personal-match-refresh",
      "search-preferences",
      "skills-experience",
      "match-priorities",
      "advanced-history"
    ]);
  });

  it("keeps match refresh directly after shared freshness", () => {
    expect(SETTINGS_SECTION_ORDER.indexOf("personal-match-refresh"))
      .toBe(SETTINGS_SECTION_ORDER.indexOf("shared-data-freshness") + 1);
  });
});

describe("match priorities", () => {
  it("normalizes arbitrary values to integer percentages totaling 100", () => {
    const normalized = normalizeMatchPriorities({ title_match: 73, required_skill_match: 12 });
    expect(totalMatchPriorities(normalized)).toBe(100);
    expect(MATCH_PRIORITY_KEYS.every((key) => Number.isInteger(normalized[key]))).toBe(true);
  });

  it("redistributes changes while preserving locked values", () => {
    const current = { ...MATCH_PRIORITY_PRESETS.balanced };
    const updated = redistributeMatchPriority(current, "title_match", 50, { salary_match: true });
    expect(updated.salary_match).toBe(current.salary_match);
    expect(updated.title_match).toBe(50);
    expect(totalMatchPriorities(updated)).toBe(100);
  });

  it("ships presets that total exactly 100", () => {
    Object.values(MATCH_PRIORITY_PRESETS).forEach((preset) => {
      expect(totalMatchPriorities(preset)).toBe(100);
    });
  });
});

describe("tag helpers", () => {
  it("normalizes custom values and deduplicates case-insensitively", () => {
    expect(addTagValue(["Power BI"], "  power   bi  ")).toEqual(["Power BI"]);
    expect(addTagValue(["Power BI"], "Clinical Operations")).toEqual([
      "Power BI",
      "Clinical Operations"
    ]);
  });

  it("searches labeled options and omits selected values", () => {
    const options = [
      { value: "US", label: "United States" },
      { value: "GB", label: "United Kingdom" }
    ];
    expect(searchableOptions(options, "unit", ["US"])).toEqual([
      { value: "GB", label: "United Kingdom" }
    ]);
  });

  it("merges paginated suggestions without case-insensitive duplicates", () => {
    expect(mergePreferenceOptions(
      [{ value: "New York", label: "New York" }],
      [
        { value: "new york", label: "new york" },
        { value: "Toronto", label: "Toronto" }
      ]
    )).toEqual([
      { value: "New York", label: "New York" },
      { value: "Toronto", label: "Toronto" }
    ]);
  });
});

describe("dirty settings behavior", () => {
  it("only warns after editable preferences change", () => {
    const baseline = createEmptyPreferences();
    const metadataOnly = structuredClone(baseline);
    metadataOnly.profile_completeness = 40;
    expect(preferencesAreDirty(baseline, metadataOnly)).toBe(false);

    const changed = structuredClone(baseline);
    changed.search_preferences.job_titles = ["Registered Nurse"];
    expect(preferencesAreDirty(baseline, changed)).toBe(true);
    expect(shouldWarnOnNavigation(true, false)).toBe(true);
    expect(shouldWarnOnNavigation(true, true)).toBe(false);
  });
});

describe("pipeline status feedback", () => {
  const failedRun = {
    run_uuid: "failed-run",
    status: "failed",
    submitted_at: "2026-07-11T22:49:26Z",
    public_error_message: "The pipeline failed. Your previous results are still available."
  };
  const completedRun = {
    run_uuid: "completed-run",
    status: "completed",
    submitted_at: "2026-07-12T04:31:47Z"
  };

  it("does not surface a historical failure after a newer successful run", () => {
    expect(latestApplicablePipelineFailure([completedRun, failedRun])).toBeUndefined();
  });

  it("surfaces the error when the latest attempt actually failed", () => {
    expect(latestApplicablePipelineFailure([failedRun, completedRun])).toBe(failedRun);
  });
});

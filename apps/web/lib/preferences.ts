import type {
  EditablePreferences,
  MatchPriorities,
  MatchPriorityKey,
  PreferenceOption,
  PreferencesDocument
} from "./types";

export const SETTINGS_SECTION_ORDER = [
  "settings-overview",
  "shared-data-freshness",
  "personal-match-refresh",
  "search-preferences",
  "skills-experience",
  "match-priorities",
  "advanced-history"
] as const;

export const MATCH_PRIORITY_KEYS: MatchPriorityKey[] = [
  "title_match",
  "required_skill_match",
  "industry_match",
  "salary_match",
  "work_arrangement_match",
  "visa_signal_match"
];

export const MATCH_PRIORITY_LABELS: Record<MatchPriorityKey, string> = {
  title_match: "Title Match",
  required_skill_match: "Required Skill Match",
  industry_match: "Industry Match",
  salary_match: "Salary Match",
  work_arrangement_match: "Work Arrangement Match",
  visa_signal_match: "Visa Signal Match"
};

export const MATCH_PRIORITY_PRESETS = {
  balanced: {
    title_match: 20,
    required_skill_match: 20,
    industry_match: 15,
    salary_match: 15,
    work_arrangement_match: 15,
    visa_signal_match: 15
  },
  skills_first: {
    title_match: 20,
    required_skill_match: 35,
    industry_match: 10,
    salary_match: 10,
    work_arrangement_match: 10,
    visa_signal_match: 15
  },
  title_industry_first: {
    title_match: 35,
    required_skill_match: 15,
    industry_match: 25,
    salary_match: 10,
    work_arrangement_match: 10,
    visa_signal_match: 5
  }
} satisfies Record<string, MatchPriorities>;

export type MatchPriorityPreset = keyof typeof MATCH_PRIORITY_PRESETS;

export const EMPTY_PREFERENCES_OPTIONS = {
  countries: [],
  locations: [],
  industries: [],
  seniority_levels: [],
  employment_types: [],
  work_arrangements: [],
  visa_options: [],
  companies: [],
  job_titles: []
};

export function createEmptyPreferences(): PreferencesDocument {
  return {
    search_preferences: {
      job_titles: [],
      industries: [],
      seniority: [],
      country: "",
      locations: [],
      work_arrangements: [],
      employment_types: [],
      visa_preferences: [],
      excluded_companies: [],
      excluded_titles: [],
      compensation: {
        minimum_salary: null,
        preferred_salary: null,
        currency: "USD",
        period: "annual"
      }
    },
    skills: [],
    skill_categories: [],
    match_priorities: { ...MATCH_PRIORITY_PRESETS.balanced },
    generated_preview: { search_titles: [], skill_aliases: [] },
    revision: {},
    revision_history: [],
    warnings: [],
    profile_completeness: 0
  };
}

function clampInteger(value: number, minimum = 0, maximum = 100) {
  const safe = Number.isFinite(value) ? Math.round(value) : minimum;
  return Math.min(maximum, Math.max(minimum, safe));
}

function allocateIntegerTotal(
  total: number,
  keys: MatchPriorityKey[],
  source: MatchPriorities
): Partial<MatchPriorities> {
  if (!keys.length) return {};
  const available = Math.max(0, Math.round(total));
  const sourceTotal = keys.reduce((sum, key) => sum + Math.max(0, source[key]), 0);
  const shares = keys.map((key, index) => {
    const raw = sourceTotal > 0
      ? (Math.max(0, source[key]) / sourceTotal) * available
      : available / keys.length;
    return { key, index, value: Math.floor(raw), fraction: raw - Math.floor(raw) };
  });
  let remainder = available - shares.reduce((sum, share) => sum + share.value, 0);
  shares
    .slice()
    .sort((left, right) => right.fraction - left.fraction || left.index - right.index)
    .forEach((share) => {
      if (remainder > 0) {
        shares[share.index].value += 1;
        remainder -= 1;
      }
    });
  return Object.fromEntries(shares.map((share) => [share.key, share.value])) as Partial<MatchPriorities>;
}

export function normalizeMatchPriorities(value: Partial<MatchPriorities>): MatchPriorities {
  const source = Object.fromEntries(
    MATCH_PRIORITY_KEYS.map((key) => [key, clampInteger(value[key] ?? 0)])
  ) as MatchPriorities;
  return {
    ...source,
    ...allocateIntegerTotal(100, MATCH_PRIORITY_KEYS, source)
  };
}

export function redistributeMatchPriority(
  current: MatchPriorities,
  changedKey: MatchPriorityKey,
  requestedValue: number,
  locked: Partial<Record<MatchPriorityKey, boolean>> = {}
): MatchPriorities {
  const normalized = normalizeMatchPriorities(current);
  if (locked[changedKey]) return normalized;

  const lockedKeys = MATCH_PRIORITY_KEYS.filter((key) => key !== changedKey && locked[key]);
  const adjustableKeys = MATCH_PRIORITY_KEYS.filter((key) => key !== changedKey && !locked[key]);
  const lockedTotal = lockedKeys.reduce((sum, key) => sum + normalized[key], 0);
  const maximum = Math.max(0, 100 - lockedTotal);
  const changedValue = adjustableKeys.length
    ? clampInteger(requestedValue, 0, maximum)
    : maximum;
  const remaining = Math.max(0, 100 - lockedTotal - changedValue);
  const allocated = allocateIntegerTotal(remaining, adjustableKeys, normalized);

  return Object.fromEntries(
    MATCH_PRIORITY_KEYS.map((key) => {
      if (key === changedKey) return [key, changedValue];
      if (locked[key]) return [key, normalized[key]];
      return [key, allocated[key] ?? 0];
    })
  ) as MatchPriorities;
}

export function totalMatchPriorities(value: MatchPriorities) {
  return MATCH_PRIORITY_KEYS.reduce((sum, key) => sum + value[key], 0);
}

export function normalizeTag(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

export function addTagValue(values: string[], candidate: string, maximum = 50) {
  const normalized = normalizeTag(candidate);
  if (!normalized || normalized.length > 120 || values.length >= maximum) return values;
  if (values.some((value) => value.toLocaleLowerCase() === normalized.toLocaleLowerCase())) return values;
  return [...values, normalized];
}

export function removeTagValue(values: string[], candidate: string) {
  return values.filter((value) => value.toLocaleLowerCase() !== candidate.toLocaleLowerCase());
}

export function searchableOptions(
  options: PreferenceOption[],
  query: string,
  selected: string[]
) {
  const normalizedQuery = normalizeTag(query).toLocaleLowerCase();
  const selectedValues = new Set(selected.map((value) => value.toLocaleLowerCase()));
  return options.filter((option) => {
    if (selectedValues.has(option.value.toLocaleLowerCase())) return false;
    return !normalizedQuery
      || option.label.toLocaleLowerCase().includes(normalizedQuery)
      || option.value.toLocaleLowerCase().includes(normalizedQuery);
  });
}

export function mergePreferenceOptions(...groups: PreferenceOption[][]) {
  const seen = new Set<string>();
  return groups.flatMap((group) => group.filter((option) => {
    const key = option.value.toLocaleLowerCase();
    if (!option.value || seen.has(key)) return false;
    seen.add(key);
    return true;
  }));
}

export function editablePreferences(value: PreferencesDocument): EditablePreferences {
  return {
    search_preferences: value.search_preferences,
    skills: value.skills,
    skill_categories: value.skill_categories,
    match_priorities: value.match_priorities
  };
}

export function preferenceFingerprint(value: PreferencesDocument) {
  return JSON.stringify(editablePreferences(value));
}

export function preferencesAreDirty(baseline: PreferencesDocument, current: PreferencesDocument) {
  return preferenceFingerprint(baseline) !== preferenceFingerprint(current);
}

export function shouldWarnOnNavigation(dirty: boolean, saving: boolean) {
  return dirty && !saving;
}

export function validatePreferences(value: PreferencesDocument) {
  const errors: string[] = [];
  const compensation = value.search_preferences.compensation;
  if (!value.search_preferences.job_titles.length) errors.push("Add at least one job title.");
  if (value.skills.some((skill) => !normalizeTag(skill.name))) errors.push("Skills cannot be blank.");
  if (compensation.minimum_salary !== null && compensation.minimum_salary < 0) {
    errors.push("Minimum salary cannot be negative.");
  }
  if (compensation.preferred_salary !== null && compensation.preferred_salary < 0) {
    errors.push("Preferred salary cannot be negative.");
  }
  if (
    compensation.minimum_salary !== null
    && compensation.preferred_salary !== null
    && compensation.preferred_salary < compensation.minimum_salary
  ) {
    errors.push("Preferred salary cannot be lower than minimum salary.");
  }
  if (
    (compensation.minimum_salary !== null || compensation.preferred_salary !== null)
    && !/^[A-Z]{3}$/.test(compensation.currency)
  ) {
    errors.push("Choose a three-letter currency code for salary preferences.");
  }
  if (totalMatchPriorities(value.match_priorities) !== 100) {
    errors.push("Match priorities must total exactly 100%.");
  }
  return errors;
}

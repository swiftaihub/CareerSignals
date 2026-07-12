import type {
  AdminActionResponse,
  AdminAuditList,
  AdminConnectorRun,
  AdminConnectorRunList,
  AdminMetrics,
  AdminUser,
  AdminUserList,
  CategorySummaryRow,
  CompanyPriorityRow,
  ConfigDocument,
  ConfigSummary,
  ConfigType,
  ConfigVersion,
  CurrentUser,
  DashboardSummary,
  DataFreshness,
  Job,
  JobFacets,
  JobFilterOptions,
  JobFilters,
  PaginatedJobs,
  PipelineRunList,
  PreferenceDynamicOptionKind,
  PreferenceOption,
  PreferencesDocument,
  PreferencesGeneratedPreview,
  PreferencesOptions,
  PreferencesPreviewResponse,
  SkillGapRow,
  UserPipelineRun
} from "@/lib/types";
import { createEmptyPreferences, normalizeMatchPriorities } from "@/lib/preferences";

const BFF_BASE_URL = "/api/backend";

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown; redirectOnAuthError?: boolean };

export class ApiClientError extends Error {
  status: number;
  errorCode?: string;
  resetsAt?: string;
  detail: string;
  error_code?: string;
  resets_at?: string;

  constructor(message: string, status: number, errorCode?: string, resetsAt?: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.errorCode = errorCode;
    this.resetsAt = resetsAt;
    this.detail = message;
    this.error_code = errorCode;
    this.resets_at = resetsAt;
  }
}

function paramsFrom(filters: object) {
  const params = new URLSearchParams();
  Object.entries(filters as Record<string, unknown>).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function normalizeGeneratedPreview(value: unknown): PreferencesGeneratedPreview {
  const source = isRecord(value) ? value : {};
  const searchTitles = Array.isArray(source.search_titles) ? source.search_titles : [];
  const skillAliases = Array.isArray(source.skill_aliases) ? source.skill_aliases : [];
  return {
    search_titles: searchTitles.flatMap((item) => {
      if (!isRecord(item)) return [];
      const title = typeof item.title === "string"
        ? item.title
        : typeof item.job_title === "string"
          ? item.job_title
          : "";
      if (!title) return [];
      return [{
        title,
        variations: stringArray(item.variations ?? item.variants)
      }];
    }),
    skill_aliases: skillAliases.flatMap((item) => {
      if (!isRecord(item) || typeof item.canonical !== "string") return [];
      return [{
        canonical: item.canonical,
        aliases: stringArray(item.aliases),
        category: typeof item.category === "string" ? item.category : null,
        source: typeof item.source === "string" ? item.source : null,
        confidence: typeof item.confidence === "number" ? item.confidence : null
      }];
    })
  };
}

function normalizePreferencesDocument(value: unknown): PreferencesDocument {
  const wrapper = isRecord(value) ? value : {};
  const source = isRecord(wrapper.preferences) ? wrapper.preferences : wrapper;
  const defaults = createEmptyPreferences();
  const search = isRecord(source.search_preferences) ? source.search_preferences : {};
  const compensation = isRecord(search.compensation) ? search.compensation : {};
  const revision = isRecord(source.revision) ? source.revision : {};
  const skills = Array.isArray(source.skills) ? source.skills : [];
  const history = Array.isArray(source.revision_history)
    ? source.revision_history
    : Array.isArray(source.history)
      ? source.history
      : [];

  return {
    search_preferences: {
      job_titles: stringArray(search.job_titles),
      industries: stringArray(search.industries),
      seniority: stringArray(search.seniority),
      country: typeof search.country === "string" ? search.country : "",
      locations: stringArray(search.locations),
      work_arrangements: stringArray(search.work_arrangements),
      employment_types: stringArray(search.employment_types),
      visa_preferences: stringArray(search.visa_preferences),
      excluded_companies: stringArray(search.excluded_companies),
      excluded_titles: stringArray(search.excluded_titles),
      compensation: {
        minimum_salary: typeof compensation.minimum_salary === "number" ? compensation.minimum_salary : null,
        preferred_salary: typeof compensation.preferred_salary === "number" ? compensation.preferred_salary : null,
        currency: typeof compensation.currency === "string" ? compensation.currency.toUpperCase() : "USD",
        period: typeof compensation.period === "string"
          ? compensation.period
          : typeof compensation.salary_period === "string"
            ? compensation.salary_period
            : "annual"
      }
    },
    skills: skills.flatMap((item) => {
      if (typeof item === "string") return [{ name: item, category: null }];
      if (!isRecord(item) || typeof item.name !== "string") return [];
      return [{ name: item.name, category: typeof item.category === "string" ? item.category : null }];
    }),
    skill_categories: stringArray(source.skill_categories),
    match_priorities: normalizeMatchPriorities(
      isRecord(source.match_priorities) ? source.match_priorities : defaults.match_priorities
    ),
    generated_preview: normalizeGeneratedPreview(source.generated_preview),
    revision: {
      bundle_uuid: typeof revision.bundle_uuid === "string"
        ? revision.bundle_uuid
        : typeof revision.bundle_revision_uuid === "string"
          ? revision.bundle_revision_uuid
          : null,
      revision: typeof revision.revision === "number" ? revision.revision : null,
      config_revision_map: isRecord(revision.config_revision_map)
        ? revision.config_revision_map as Record<string, number>
        : {},
      generator_version: typeof revision.generator_version === "string" ? revision.generator_version : null,
      created_at: typeof revision.created_at === "string" ? revision.created_at : null
    },
    revision_history: history.flatMap((item) => {
      if (!isRecord(item)) return [];
      return [{
        bundle_uuid: typeof item.bundle_uuid === "string"
          ? item.bundle_uuid
          : typeof item.bundle_revision_uuid === "string"
            ? item.bundle_revision_uuid
            : null,
        revision: typeof item.revision === "number" ? item.revision : null,
        generator_version: typeof item.generator_version === "string" ? item.generator_version : null,
        created_at: typeof item.created_at === "string" ? item.created_at : null,
        status: typeof item.status === "string" ? item.status : null,
        created_by: typeof item.created_by === "string" ? item.created_by : null
      }];
    }),
    warnings: stringArray(source.warnings),
    profile_completeness: typeof source.profile_completeness === "number"
      ? Math.min(100, Math.max(0, Math.round(source.profile_completeness)))
      : 0
  };
}

function normalizeOptionList(value: unknown): PreferenceOption[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.flatMap((item) => {
    const option = typeof item === "string"
      ? { value: item, label: item }
      : isRecord(item) && typeof item.value === "string"
        ? { value: item.value, label: typeof item.label === "string" ? item.label : item.value }
        : [];
    if (Array.isArray(option) || !option.value || seen.has(option.value.toLocaleLowerCase())) return [];
    seen.add(option.value.toLocaleLowerCase());
    return [option];
  });
}

function preferencePayload(value: PreferencesDocument) {
  return {
    search_preferences: {
      ...value.search_preferences,
      compensation: {
        minimum_salary: value.search_preferences.compensation.minimum_salary,
        preferred_salary: value.search_preferences.compensation.preferred_salary,
        currency: value.search_preferences.compensation.currency,
        period: value.search_preferences.compensation.period
      }
    },
    skills: value.skills.map((skill) => ({ name: skill.name, category: skill.category || null })),
    skill_categories: value.skill_categories,
    match_priorities: value.match_priorities
  };
}

function preferenceWriteBody(value: PreferencesDocument) {
  return {
    ...preferencePayload(value),
    expected_revision: value.revision.revision ?? null
  };
}

function redirectFor(error: ApiClientError) {
  if (typeof window === "undefined") return;
  const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
  if (error.status === 401) window.location.assign(`/login?next=${next}`);
  else if (error.errorCode === "ACCOUNT_PENDING") window.location.assign("/pending");
  else if (error.errorCode === "ACCOUNT_EXPIRED") window.location.assign("/account-expired");
  else if (error.errorCode === "ACCOUNT_SUSPENDED" || error.errorCode === "ACCOUNT_DELETED") {
    window.location.assign(`/login?error=${encodeURIComponent(error.errorCode)}`);
  }
}

async function parseError(response: Response) {
  let detail = "The request could not be completed.";
  let errorCode: string | undefined;
  let resetsAt: string | undefined;
  try {
    const payload = await response.json();
    const source = typeof payload?.detail === "object" ? payload.detail : payload;
    detail = typeof source?.detail === "string"
      ? source.detail
      : typeof payload?.detail === "string"
        ? payload.detail
        : detail;
    errorCode = source?.error_code || payload?.error_code;
    resetsAt = source?.resets_at || payload?.resets_at;
  } catch {
    // Keep the generic public message.
  }
  return new ApiClientError(detail, response.status, errorCode, resetsAt);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, redirectOnAuthError = true, ...init } = options;
  let response: Response;
  try {
    response = await fetch(`${BFF_BASE_URL}${path}`, {
      ...init,
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(init.headers || {})
      },
      body: body === undefined ? undefined : JSON.stringify(body)
    });
  } catch {
    throw new ApiClientError("The CareerSignals service is temporarily unavailable.", 503, "API_UNREACHABLE");
  }

  if (!response.ok) {
    const error = await parseError(response);
    if (redirectOnAuthError) redirectFor(error);
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const getMe = () => apiRequest<CurrentUser>("/api/me");
export const getDashboardSummary = () => apiRequest<DashboardSummary>("/api/dashboard/summary");
export const getJobs = (filters: JobFilters = {}) => apiRequest<PaginatedJobs>(`/api/jobs${paramsFrom(filters)}`);
export const getJobFilterOptions = () => apiRequest<JobFilterOptions>("/api/jobs/filter-options");
export const getJobFacets = () => apiRequest<JobFacets>("/api/jobs/facets");
export const getJob = (jobId: string) => apiRequest<Job>(`/api/jobs/${encodeURIComponent(jobId)}`);
export const getTopMatches = () => apiRequest<Job[]>("/api/top-matches");
export const getCategorySummary = () => apiRequest<CategorySummaryRow[]>("/api/category-summary");
export const getSkillGap = () => apiRequest<SkillGapRow[]>("/api/skill-gap");
export const getCompanyPriority = () => apiRequest<CompanyPriorityRow[]>("/api/company-priority");
export const getDataFreshness = () => apiRequest<DataFreshness>("/api/data-freshness");

export async function getPreferences() {
  return normalizePreferencesDocument(await apiRequest<unknown>("/api/preferences"));
}

export async function getPreferencesOptions(filters: {
  kind?: PreferenceDynamicOptionKind;
  q?: string;
  limit?: number;
  offset?: number;
} = {}) {
  const value = await apiRequest<unknown>(`/api/preferences/options${paramsFrom(filters)}`);
  const source = isRecord(value) ? value : {};
  return {
    countries: normalizeOptionList(source.countries),
    locations: normalizeOptionList(source.locations),
    industries: normalizeOptionList(source.industries),
    seniority_levels: normalizeOptionList(source.seniority_levels),
    employment_types: normalizeOptionList(source.employment_types),
    work_arrangements: normalizeOptionList(source.work_arrangements),
    visa_options: normalizeOptionList(source.visa_options),
    companies: normalizeOptionList(source.companies),
    job_titles: normalizeOptionList(source.job_titles)
  } satisfies PreferencesOptions;
}

export async function previewPreferences(value: PreferencesDocument): Promise<PreferencesPreviewResponse> {
  const response = await apiRequest<unknown>("/api/preferences/preview", {
    method: "POST",
    body: preferencePayload(value)
  });
  const source = isRecord(response) ? response : {};
  return {
    generated_preview: normalizeGeneratedPreview(source.generated_preview ?? source),
    warnings: stringArray(source.warnings),
    profile_completeness: typeof source.profile_completeness === "number"
      ? Math.round(source.profile_completeness)
      : undefined,
    derived_candidate_profile: isRecord(source.derived_candidate_profile)
      ? source.derived_candidate_profile
      : undefined
  };
}

export async function savePreferences(value: PreferencesDocument) {
  return normalizePreferencesDocument(await apiRequest<unknown>("/api/preferences", {
    method: "PUT",
    body: preferenceWriteBody(value)
  }));
}

export async function restorePreferencesRevision(revision: string | number) {
  return normalizePreferencesDocument(await apiRequest<unknown>(
    `/api/preferences/history/${encodeURIComponent(String(revision))}/restore`,
    { method: "POST" }
  ));
}

export async function resetPreferences() {
  return normalizePreferencesDocument(await apiRequest<unknown>("/api/preferences/reset", { method: "POST" }));
}

export const updateJobStatus = (jobId: string, body: { application_status: string; notes?: string | null }) =>
  apiRequest<{ job_id: string; application_status: string; notes?: string | null; updated_at: string }>(
    `/api/jobs/${encodeURIComponent(jobId)}/status`,
    { method: "PATCH", body }
  );

export const getConfigs = () => apiRequest<ConfigSummary[]>("/api/configs");
export const getConfig = (type: ConfigType) => apiRequest<ConfigDocument>(`/api/configs/${type}`);
export const saveConfig = (type: ConfigType, override_config: Record<string, unknown>) =>
  apiRequest<ConfigDocument>(`/api/configs/${type}`, { method: "PUT", body: { override_config } });
export const resetConfig = (type: ConfigType) =>
  apiRequest<ConfigDocument>(`/api/configs/${type}/reset`, { method: "POST" });
export const resetConfigField = (type: ConfigType, field_path: string) =>
  apiRequest<ConfigDocument>(`/api/configs/${type}/reset-field`, { method: "POST", body: { field_path } });
export const getConfigVersions = (type: ConfigType) =>
  apiRequest<ConfigVersion[]>(`/api/configs/${type}/versions`);
export const restoreConfigVersion = (type: ConfigType, revision: number) =>
  apiRequest<ConfigDocument>(`/api/configs/${type}/restore/${revision}`, { method: "POST" });

export const createPipelineRun = () => apiRequest<UserPipelineRun>("/api/pipeline-runs", { method: "POST" });
export const getPipelineRuns = () => apiRequest<PipelineRunList | UserPipelineRun[]>("/api/pipeline-runs");
export const getPipelineRun = (runUuid: string) =>
  apiRequest<UserPipelineRun>(`/api/pipeline-runs/${encodeURIComponent(runUuid)}`);
export const cancelPipelineRun = (runUuid: string) =>
  apiRequest<UserPipelineRun>(`/api/pipeline-runs/${encodeURIComponent(runUuid)}/cancel`, { method: "POST" });
export async function downloadExcelExport() {
  let response: Response;
  try {
    response = await fetch(`${BFF_BASE_URL}/api/exports/excel`, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }
    });
  } catch {
    throw new ApiClientError("The CareerSignals service is temporarily unavailable.", 503, "API_UNREACHABLE");
  }
  if (!response.ok) {
    const error = await parseError(response);
    redirectFor(error);
    throw error;
  }

  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quotedName = disposition.match(/filename="([^"]+)"/i)?.[1];
  const filename = encodedName
    ? decodeURIComponent(encodedName)
    : quotedName || "careersignals-jobs.xlsx";
  const objectUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename.replace(/[\\/:*?"<>|]/g, "-");
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export const getAdminMetrics = (filters: { start_date?: string; end_date?: string; timezone?: string } = {}) =>
  apiRequest<AdminMetrics>(`/api/admin/metrics${paramsFrom(filters)}`);
export const getAdminUsers = (filters: Record<string, unknown> = {}) =>
  apiRequest<AdminUserList>(`/api/admin/users${paramsFrom(filters)}`);
export const createAdminUser = (body: Record<string, unknown>) =>
  apiRequest<AdminUser>("/api/admin/users", { method: "POST", body });
type AdminProfileAction = "activate" | "expire" | "grant-days" | "reduce-days" | "suspend" | "restore";
type AdminMessageAction = "reset-password" | "revoke-sessions";

export function mutateAdminUser(
  userUuid: string,
  action: AdminProfileAction,
  body?: Record<string, unknown>
): Promise<AdminUser>;
export function mutateAdminUser(
  userUuid: string,
  action: AdminMessageAction,
  body?: Record<string, unknown>
): Promise<AdminActionResponse>;
export function mutateAdminUser(
  userUuid: string,
  action: string,
  body?: Record<string, unknown>
): Promise<AdminUser | AdminActionResponse>;
export function mutateAdminUser(userUuid: string, action: string, body?: Record<string, unknown>) {
  return apiRequest<AdminUser | AdminActionResponse>(`/api/admin/users/${encodeURIComponent(userUuid)}/${action}`, {
    method: "POST",
    body
  });
}
export const updateAdminUser = (userUuid: string, body: Record<string, unknown>) =>
  apiRequest<AdminUser>(`/api/admin/users/${encodeURIComponent(userUuid)}`, { method: "PATCH", body });
export const deleteAdminUser = (userUuid: string) =>
  apiRequest<void>(`/api/admin/users/${encodeURIComponent(userUuid)}`, { method: "DELETE" });
export const getAdminAuditLogs = (filters: Record<string, unknown> = {}) =>
  apiRequest<AdminAuditList>(`/api/admin/audit-logs${paramsFrom(filters)}`);
export const getAdminConnectorRuns = () =>
  apiRequest<AdminConnectorRunList>("/api/admin/connector-runs");
export const createAdminConnectorRun = () =>
  apiRequest<AdminConnectorRun>("/api/admin/connector-runs", { method: "POST" });

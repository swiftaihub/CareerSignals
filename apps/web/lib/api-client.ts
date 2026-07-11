import type {
  AdminActionResponse,
  AdminAuditList,
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
  SkillGapRow,
  UserPipelineRun
} from "@/lib/types";

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

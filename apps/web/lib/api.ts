import type {
  ActionResponse,
  ApiError,
  DashboardSummary,
  DataStatus,
  Job,
  JobFilterOptions,
  JobFilters,
  PaginatedJobs,
  PipelineRunStatus,
  SkillGapRow,
  CategorySummaryRow,
  CompanyPriorityRow
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

function paramsFrom(filters: object) {
  const params = new URLSearchParams();
  Object.entries(filters as Record<string, unknown>).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") {
      return {
        detail: payload.detail,
        error_code: payload.error_code,
        resets_at: payload.resets_at,
        status: response.status
      };
    }
    if (payload?.detail?.detail) {
      return {
        detail: payload.detail.detail,
        error_code: payload.detail.error_code,
        resets_at: payload.detail.resets_at,
        status: response.status
      };
    }
    if (Array.isArray(payload?.detail)) {
      const firstError = payload.detail[0];
      return {
        detail: firstError?.msg ? `Request validation failed: ${firstError.msg}` : "Request validation failed.",
        error_code: "REQUEST_VALIDATION_ERROR",
        status: response.status
      };
    }
  } catch {
    // Fall through to the generic message below.
  }
  return {
    detail: `Request failed with status ${response.status}`,
    error_code: "REQUEST_FAILED",
    status: response.status
  };
}

function apiHostLabel() {
  try {
    const url = new URL(API_BASE_URL);
    return `${url.hostname}${url.port ? `:${url.port}` : ""}`;
  } catch {
    return API_BASE_URL;
  }
}

function networkError(error: unknown): ApiError {
  if (process.env.NODE_ENV !== "production") {
    console.debug("CareerSignal API network request failed", {
      apiBaseUrl: API_BASE_URL,
      error
    });
  }
  return {
    detail: `CareerSignal API is not reachable. Please confirm FastAPI is running on ${apiHostLabel()}. If it is running, confirm CORS allows http://localhost:3000.`,
    error_code: "API_UNREACHABLE"
  };
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store"
    });
  } catch (error) {
    throw networkError(error);
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<{ status: string }>("/api/health");
}

export function getDashboardSummary() {
  return request<DashboardSummary>("/api/dashboard/summary");
}

export function getJobs(filters: JobFilters = {}) {
  return request<PaginatedJobs>(`/api/jobs${paramsFrom(filters)}`);
}

export function getJobFilterOptions() {
  return request<JobFilterOptions>("/api/jobs/filter-options");
}

export function getJob(jobId: string) {
  return request<Job>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function getTopMatches() {
  return request<Job[]>("/api/top-matches");
}

export function getCategorySummary() {
  return request<CategorySummaryRow[]>("/api/category-summary");
}

export function getSkillGap() {
  return request<SkillGapRow[]>("/api/skill-gap");
}

export function getCompanyPriority() {
  return request<CompanyPriorityRow[]>("/api/company-priority");
}

export function getDataStatus() {
  return request<DataStatus>("/api/data/status");
}

export function updateJobStatus(
  jobId: string,
  payload: { application_status: string; notes?: string | null }
) {
  return request<{
    job_id: string;
    application_status: string;
    notes?: string | null;
    updated_at: string;
  }>(`/api/jobs/${encodeURIComponent(jobId)}/status`, {
    method: "PATCH",
    body: payload
  });
}

export function runPipeline() {
  return request<PipelineRunStatus>("/api/pipeline/run", { method: "POST" });
}

export function getPipelineRun(runId: string) {
  return request<PipelineRunStatus>(`/api/pipeline/runs/${encodeURIComponent(runId)}`);
}

export function runDbt(fullRefresh = false) {
  return request<ActionResponse>(`/api/dbt/run${paramsFrom({ full_refresh: fullRefresh })}`, {
    method: "POST"
  });
}

export function testDbt() {
  return request<ActionResponse>("/api/dbt/test", { method: "POST" });
}

export function exportExcel() {
  return request<ActionResponse>("/api/excel/export", { method: "POST" });
}

export function getExcelDownloadUrl() {
  return `${API_BASE_URL}/api/excel/download`;
}

export type ApplicationStatus =
  | "Not Applied"
  | "Saved"
  | "Applied"
  | "Interview"
  | "Rejected"
  | "Offer"
  | "Archived";

export type SortOrder = "asc" | "desc";

export interface Job {
  job_id: string;
  category_name?: string | null;
  match_tier?: string | null;
  match_score?: number | null;
  job_title?: string | null;
  normalized_title?: string | null;
  company?: string | null;
  industry?: string | null;
  location?: string | null;
  location_normalized?: string | null;
  location_group?: string | null;
  work_arrangement?: string | null;
  seniority?: string | null;
  employment_type?: string | null;
  salary_range_text?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_midpoint?: number | null;
  visa_signal?: string | null;
  visa_status?: string | null;
  visa_evidence?: string | null;
  visa_confidence?: string | null;
  required_skills?: string[];
  preferred_skills?: string[];
  all_extracted_skills?: string[];
  jd_post_link?: string | null;
  apply_link?: string | null;
  date_posted?: string | null;
  date_collected?: string | null;
  source?: string | null;
  application_status?: ApplicationStatus | string | null;
  notes?: string | null;
  application_updated_at?: string | null;
  reasoning_summary?: string | null;
}

export interface JobFilters {
  limit?: number;
  offset?: number;
  page?: number;
  page_size?: number;
  category_name?: string;
  min_match_score?: number;
  max_match_score?: number;
  company?: string;
  industry?: string;
  location?: string;
  location_group?: string;
  work_arrangement?: string;
  visa_signal?: string;
  application_status?: string;
  search?: string;
  posted_start_date?: string;
  posted_end_date?: string;
  sort_by?: string;
  sort_order?: SortOrder;
}

export interface JobFilterOptions {
  categories: string[];
  companies: string[];
  industries: string[];
  locations: string[];
}

export interface LocationFacet {
  group: string;
  value: string;
  count: number;
}

export interface LocationGroupFacet {
  group: string;
  count: number;
}

export interface JobFacets {
  locations: LocationFacet[];
  location_groups: LocationGroupFacet[];
}

export interface PaginatedJobs {
  items: Job[];
  total: number;
  page: number;
  page_size: number;
  limit: number;
  offset: number;
}

export interface CategorySummaryRow {
  category_name: string;
  jobs_found?: number | null;
  excellent_matches?: number | null;
  strong_matches?: number | null;
  good_matches?: number | null;
  average_match_score?: number | null;
  average_salary_midpoint?: number | null;
  remote_count?: number | null;
  hybrid_count?: number | null;
  onsite_count?: number | null;
  unknown_work_arrangement_count?: number | null;
  positive_visa_signal_count?: number | null;
  negative_visa_signal_count?: number | null;
  unknown_visa_signal_count?: number | null;
}

export interface SkillGapRow {
  skill: string;
  skill_group?: string | null;
  appears_in_job_count?: number | null;
  appears_in_job_pct?: number | null;
  in_candidate_profile?: string | boolean | null;
  gap_priority?: string | null;
  example_matching_job_titles?: string | null;
}

export interface CompanyPriorityRow {
  company: string;
  industry?: string | null;
  matching_roles_count?: number | null;
  average_match_score?: number | null;
  highest_match_score?: number | null;
  average_salary_midpoint?: number | null;
  best_matching_role?: string | null;
  visa_signal_summary?: string | null;
  priority?: string | null;
}

export interface DataStatus {
  data_mode?: string | null;
  database?: string | null;
  motherduck_database?: string | null;
  mart_tables_available?: boolean | null;
  last_pipeline_run_at?: string | null;
  last_pipeline_run?: string | null;
  last_dbt_run_at?: string | null;
  last_dbt_run?: string | null;
  last_dbt_test_at?: string | null;
  excel_path?: string | null;
  excel_exists?: boolean | null;
  excel_source?: string | null;
  local_mode_available?: boolean | null;
  motherduck_mode_available?: boolean | null;
  dbt_project_dir?: string | null;
  dbt_profiles_dir?: string | null;
  configured_sources?: string[];
  job_sources?: string[];
  latest_run_status?: string | null;
  pipeline_quota?: PipelineQuota | null;
}

export interface DistributionRow {
  label: string;
  count: number;
}

export interface DashboardSummary {
  data_status: DataStatus;
  metrics: {
    total_jobs: number;
    top_matches: number;
    average_match_score?: number | null;
    average_salary_midpoint?: number | null;
    remote_or_hybrid_roles: number;
    positive_or_unknown_visa_roles: number;
  };
  category_summary: CategorySummaryRow[];
  top_matches_preview: Job[];
  visa_signal_distribution: DistributionRow[];
  work_arrangement_distribution: DistributionRow[];
  match_tier_distribution: DistributionRow[];
}

export interface ApiError {
  detail: string;
  error_code?: string;
  status?: number;
  resets_at?: string;
}

export interface ActionResponse {
  status: string;
  output_path?: string;
  [key: string]: unknown;
}

export interface PipelineQuota {
  limit: number;
  used: number;
  remaining: number;
  window_start: string;
  window_end: string;
  resets_at: string;
}

export interface PipelineRunMessage {
  timestamp: string;
  level: "info" | "warning" | "error" | string;
  message: string;
}

export type PipelineRunState = "queued" | "running" | "completed" | "failed";

export interface PipelineRunStatus {
  run_id: string;
  status: PipelineRunState | string;
  started_at: string;
  completed_at?: string | null;
  messages: PipelineRunMessage[];
  summary?: Record<string, unknown> | null;
  quota?: PipelineQuota;
}

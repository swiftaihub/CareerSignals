export type ApplicationStatus =
  | "Not Applied"
  | "Saved"
  | "Applied"
  | "Interview"
  | "Rejected"
  | "Offer"
  | "Archived";

export type SortOrder = "asc" | "desc";

export type UserRole = "user" | "admin" | "demo";
export type AccountStatus = "pending" | "active" | "expired" | "suspended" | "deleted";

export interface CurrentUser {
  user_uuid: string;
  username: string;
  email?: string | null;
  role: UserRole;
  account_status: AccountStatus;
  created_at: string;
  activated_at?: string | null;
  expires_at?: string | null;
  remaining_days?: number | null;
  last_login_at?: string | null;
  last_activity_at?: string | null;
  last_successful_pipeline_run_uuid?: string | null;
  is_demo: boolean;
}

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

export type ConfigType = "candidate_profile" | "jobs_config" | "skill_taxonomy";

export interface ConfigSummary {
  config_type: ConfigType;
  revision: number;
  updated_at?: string | null;
  is_overridden?: boolean;
}

export interface ConfigDocument extends ConfigSummary {
  default_config: Record<string, unknown>;
  override_config: Record<string, unknown>;
  effective_config: Record<string, unknown>;
  field_sources: Record<string, "default" | "override" | string>;
}

export interface ConfigVersion {
  revision: number;
  override_config: Record<string, unknown>;
  change_source?: string;
  created_at: string;
}

export interface PreferenceOption {
  value: string;
  label: string;
}

export interface CompensationPreferences {
  minimum_salary: number | null;
  preferred_salary: number | null;
  currency: string;
  period: string;
}

export interface SearchPreferences {
  job_titles: string[];
  industries: string[];
  seniority: string[];
  country: string;
  locations: string[];
  work_arrangements: string[];
  employment_types: string[];
  visa_preferences: string[];
  excluded_companies: string[];
  excluded_titles: string[];
  compensation: CompensationPreferences;
}

export interface PreferenceSkill {
  name: string;
  category?: string | null;
}

export type MatchPriorityKey =
  | "title_match"
  | "required_skill_match"
  | "industry_match"
  | "salary_match"
  | "work_arrangement_match"
  | "visa_signal_match";

export type MatchPriorities = Record<MatchPriorityKey, number>;

export interface GeneratedSearchTitle {
  title: string;
  variations: string[];
}

export interface GeneratedSkillAlias {
  canonical: string;
  aliases: string[];
  category?: string | null;
  source?: string | null;
  confidence?: number | null;
}

export interface PreferencesGeneratedPreview {
  search_titles: GeneratedSearchTitle[];
  skill_aliases: GeneratedSkillAlias[];
}

export interface PreferencesRevision {
  bundle_uuid?: string | null;
  revision?: number | null;
  config_revision_map?: Record<string, number>;
  generator_version?: string | null;
  created_at?: string | null;
}

export interface PreferencesRevisionEntry extends PreferencesRevision {
  status?: string | null;
  created_by?: string | null;
}

export interface PreferencesDocument {
  search_preferences: SearchPreferences;
  skills: PreferenceSkill[];
  skill_categories: string[];
  match_priorities: MatchPriorities;
  generated_preview: PreferencesGeneratedPreview;
  revision: PreferencesRevision;
  revision_history: PreferencesRevisionEntry[];
  warnings: string[];
  profile_completeness: number;
}

export type EditablePreferences = Pick<
  PreferencesDocument,
  "search_preferences" | "skills" | "skill_categories" | "match_priorities"
>;

export interface PreferencesOptions {
  countries: PreferenceOption[];
  locations: PreferenceOption[];
  industries: PreferenceOption[];
  seniority_levels: PreferenceOption[];
  employment_types: PreferenceOption[];
  work_arrangements: PreferenceOption[];
  visa_options: PreferenceOption[];
  companies: PreferenceOption[];
  job_titles: PreferenceOption[];
}

export type PreferenceDynamicOptionKind =
  | "locations"
  | "industries"
  | "companies"
  | "job_titles";

export interface PreferencesPreviewResponse {
  generated_preview: PreferencesGeneratedPreview;
  warnings: string[];
  profile_completeness?: number;
  derived_candidate_profile?: Record<string, unknown>;
}

export interface DataFreshnessSource {
  source_name: string;
  last_successful_refresh_at?: string | null;
  records_retained?: number;
  status: string;
  public_status_message?: string | null;
}

export interface DataFreshness {
  overall: {
    last_successful_refresh_at?: string | null;
    next_scheduled_refresh_at?: string | null;
    data_as_of?: string | null;
    is_stale: boolean;
    status: string;
  };
  sources: DataFreshnessSource[];
}

export interface ActionResponse {
  status: string;
  output_path?: string;
  [key: string]: unknown;
}

export interface PipelineQuota {
  limit: number | null;
  used: number;
  remaining: number | null;
  window_start: string;
  window_end: string;
  resets_at: string;
}

export interface PipelineRunMessage {
  timestamp: string;
  level: "info" | "warning" | "error" | string;
  message: string;
}

export type PipelineRunState = "waiting_for_global" | "queued" | "running" | "completed" | "failed" | "cancelled";

export interface PipelineRunStatus {
  run_id: string;
  status: PipelineRunState | string;
  started_at: string;
  completed_at?: string | null;
  messages: PipelineRunMessage[];
  summary?: Record<string, unknown> | null;
  quota?: PipelineQuota;
}

export interface UserPipelineRunEvent {
  event_uuid?: string;
  event_level: string;
  event_type?: string;
  message: string;
  created_at: string;
}

export interface UserPipelineRun {
  run_uuid: string;
  status: PipelineRunState | string;
  submitted_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  published_at?: string | null;
  config_hash?: string;
  source_connector_run_uuid?: string | null;
  is_bootstrap_run?: boolean;
  bootstrap_uuid?: string | null;
  bootstrap_status?: string | null;
  trigger_type?: string | null;
  jobs_considered?: number;
  jobs_matched?: number;
  public_error_message?: string | null;
  events?: UserPipelineRunEvent[];
  is_current_result?: boolean;
}

export interface PipelineRunList {
  items: UserPipelineRun[];
  total?: number;
}

export interface ExcelExportResponse {
  export_uuid?: string;
  status: string;
  download_url?: string;
  expires_at?: string;
}

export interface TimeSeriesPoint {
  date?: string;
  hour?: number;
  label?: string;
  value?: number;
  count?: number;
  successful?: number;
  failed?: number;
  total?: number;
}

export interface AdminMetrics {
  total_registered_users: number;
  new_registered_users: number;
  pending_users: number;
  active_users: number;
  expired_users: number;
  suspended_users?: number;
  estimated_mrr_cents: number;
  actual_monthly_revenue_cents: number;
  total_revenue_cents: number;
  pipeline_success_rate: number;
  average_pipeline_duration_seconds?: number;
  registrations_by_day?: TimeSeriesPoint[];
  active_users_by_day?: TimeSeriesPoint[];
  activity_by_hour?: TimeSeriesPoint[];
  pipeline_runs_by_day?: TimeSeriesPoint[];
  revenue_events_by_day?: TimeSeriesPoint[];
  expiration_outlook?: TimeSeriesPoint[];
}

export interface AdminUser {
  user_uuid: string;
  username: string;
  email?: string | null;
  role: UserRole;
  account_status: AccountStatus;
  created_at: string;
  activated_at?: string | null;
  expires_at?: string | null;
  remaining_days?: number | null;
  last_login_at?: string | null;
  last_activity_at?: string | null;
  last_successful_pipeline_run_uuid?: string | null;
  pipeline_quota_reset_at?: string | null;
}

export interface AdminUserList {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminActionResponse {
  detail: string;
}

export interface AdminAuditLog {
  audit_uuid?: string;
  admin_user_uuid?: string;
  target_user_uuid?: string | null;
  action: string;
  details?: Record<string, unknown>;
  created_at: string;
  request_id?: string | null;
}

export interface AdminAuditList {
  items: AdminAuditLog[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminConnectorRun {
  connector_run_uuid: string;
  status: string;
  trigger_type: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  jobs_fetched?: number;
  jobs_retained?: number;
  jobs_published?: number;
  included_user_count?: number;
  acquisition_query_count?: number;
  public_status_message?: string | null;
}

export interface AdminConnectorRunList {
  items: AdminConnectorRun[];
}

"use client";

import { useCallback, useEffect, useState } from "react";

import { useAccount } from "@/components/auth/account-context";
import { JobDetailDrawer } from "@/components/jobs/job-detail-drawer";
import { JobFilters } from "@/components/jobs/job-filters";
import { JobsTable } from "@/components/jobs/jobs-table";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { getJobFacets, getJobFilterOptions, getJobs, updateJobStatus } from "@/lib/api";
import type {
  ApiError,
  Job,
  JobFacets,
  JobFilterOptions,
  JobFilters as JobFilterValues,
  PaginatedJobs,
  SortOrder
} from "@/lib/types";

const DEFAULT_FILTERS: JobFilterValues = {
  page: 1,
  page_size: 25,
  sort_by: "match_score",
  sort_order: "desc"
};

const EMPTY_FILTER_OPTIONS: JobFilterOptions = {
  categories: [],
  companies: [],
  industries: [],
  locations: []
};

const EMPTY_FACETS: JobFacets = {
  locations: [],
  location_groups: []
};

export default function JobsPage() {
  const user = useAccount();
  const readOnly = Boolean(user?.is_demo);
  const [filters, setFilters] = useState<JobFilterValues>(DEFAULT_FILTERS);
  const [filterOptions, setFilterOptions] = useState<JobFilterOptions>(EMPTY_FILTER_OPTIONS);
  const [facets, setFacets] = useState<JobFacets>(EMPTY_FACETS);
  const [facetsLoading, setFacetsLoading] = useState(true);
  const [data, setData] = useState<PaginatedJobs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [drawerNotes, setDrawerNotes] = useState("");
  const [statusUpdating, setStatusUpdating] = useState(false);

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getJobs(filters));
    } catch (requestError) {
      setError(requestError as ApiError);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    Promise.all([getJobFilterOptions(), getJobFacets()])
      .then(([nextFilterOptions, nextFacets]) => {
        setFilterOptions(nextFilterOptions);
        setFacets(nextFacets);
      })
      .catch((requestError) => setError(requestError as ApiError))
      .finally(() => setFacetsLoading(false));
  }, []);

  function selectJob(job: Job) {
    setSelectedJob(job);
    setDrawerNotes(job.notes || "");
  }

  async function changeStatus(job: Job, status: string, notes?: string) {
    if (readOnly) return;
    setStatusUpdating(true);
    try {
      const result = await updateJobStatus(job.job_id, {
        application_status: status,
        notes: notes ?? job.notes ?? null
      });
      setData((current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.job_id === job.job_id
                  ? {
                      ...item,
                      application_status: result.application_status,
                      notes: result.notes,
                      application_updated_at: result.updated_at
                    }
                  : item
              )
            }
          : current
      );
      setSelectedJob((current) =>
        current?.job_id === job.job_id
          ? {
              ...current,
              application_status: result.application_status,
              notes: result.notes,
              application_updated_at: result.updated_at
            }
          : current
      );
    } catch (requestError) {
      setError(requestError as ApiError);
    } finally {
      setStatusUpdating(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Job Explorer"
        title="Search, filter, and work your role pipeline"
        description="Use the scored mart data through FastAPI, keep statuses current, and drill into role-fit details without exposing warehouse credentials."
      />

      <JobFilters
        facets={facets}
        facetsLoading={facetsLoading}
        filters={filters}
        options={filterOptions}
        onChange={setFilters}
        onReset={() => setFilters(DEFAULT_FILTERS)}
      />

      <div className="mt-5">
        {error ? <ErrorState error={error} /> : null}
        {loading ? (
          <LoadingState label="Loading jobs..." />
        ) : data ? (
          <JobsTable
            jobs={data.items}
            page={data.page}
            pageSize={data.page_size}
            sortBy={filters.sort_by || "match_score"}
            sortOrder={(filters.sort_order || "desc") as SortOrder}
            total={data.total}
            onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
            onSelectJob={selectJob}
            onSortChange={(sort_by, sort_order) =>
              setFilters((current) => ({ ...current, page: 1, sort_by, sort_order }))
            }
            onStatusChange={(job, status) => changeStatus(job, status)}
            readOnly={readOnly}
          />
        ) : null}
      </div>

      <JobDetailDrawer
        job={selectedJob}
        notes={drawerNotes}
        open={Boolean(selectedJob)}
        updating={statusUpdating}
        onClose={() => setSelectedJob(null)}
        onNotesChange={setDrawerNotes}
        onStatusChange={changeStatus}
        readOnly={readOnly}
      />
    </AppShell>
  );
}

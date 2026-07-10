"use client";

import { useEffect, useState } from "react";

import { ApplicationStatusSelect } from "@/components/jobs/application-status-select";
import { JobLinkButtons } from "@/components/jobs/job-link-buttons";
import { MatchScoreBadge } from "@/components/jobs/match-score-badge";
import { VisaSignalBadge } from "@/components/jobs/visa-signal-badge";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { getTopMatches, updateJobStatus } from "@/lib/api";
import { formatCurrency, formatList, formatNullable } from "@/lib/formatters";
import type { ApiError, Job } from "@/lib/types";

export default function TopMatchesPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    getTopMatches()
      .then(setJobs)
      .catch((requestError) => setError(requestError as ApiError))
      .finally(() => setLoading(false));
  }, []);

  async function changeStatus(job: Job, status: string) {
    setUpdatingId(job.job_id);
    try {
      const result = await updateJobStatus(job.job_id, {
        application_status: status,
        notes: job.notes || null
      });
      setJobs((current) =>
        current.map((item) =>
          item.job_id === job.job_id
            ? { ...item, application_status: result.application_status, application_updated_at: result.updated_at }
            : item
        )
      );
    } catch (requestError) {
      setError(requestError as ApiError);
    } finally {
      setUpdatingId(null);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Top Matches"
        title="Roles most worth your attention today"
        description="A focused review queue for high-scoring opportunities, with enough context to decide whether to save, apply, or archive."
      />

      {error ? <ErrorState error={error} title="Top matches unavailable" /> : null}
      {loading ? <LoadingState label="Loading top matches..." /> : null}
      {!loading && !error && !jobs.length ? (
        <EmptyState
          title="No top matches yet"
          description="Run the pipeline or broaden your scoring criteria to build today's high-fit review queue."
        />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        {jobs.map((job) => (
          <article key={job.job_id} className="rounded-lg border border-border bg-card p-5 shadow-soft">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap gap-2">
                  <MatchScoreBadge score={job.match_score} tier={job.match_tier} />
                  <VisaSignalBadge signal={job.visa_signal} />
                </div>
                <h2 className="mt-4 text-lg font-bold text-foreground">
                  {formatNullable(job.job_title)}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {formatNullable(job.company)} - {formatNullable(job.location)}
                </p>
              </div>
              <ApplicationStatusSelect
                disabled={updatingId === job.job_id}
                value={job.application_status}
                onChange={(value) => changeStatus(job, value)}
              />
            </div>
            <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
              <div>
                <div className="text-xs font-semibold uppercase text-muted-foreground">Salary</div>
                <div className="mt-1">{formatCurrency(job.salary_midpoint)}</div>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase text-muted-foreground">Work</div>
                <div className="mt-1">{formatNullable(job.work_arrangement)}</div>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase text-muted-foreground">Category</div>
                <div className="mt-1">{formatNullable(job.category_name)}</div>
              </div>
            </div>
            <p className="mt-4 rounded-lg border border-border bg-background p-3 text-sm leading-6 text-muted-foreground">
              {formatNullable(job.reasoning_summary)}
            </p>
            <div className="mt-4 text-sm">
              <span className="font-semibold">Top skills: </span>
              <span className="text-muted-foreground">{formatList(job.all_extracted_skills?.slice(0, 8))}</span>
            </div>
            <div className="mt-4">
              <JobLinkButtons job={job} />
            </div>
          </article>
        ))}
      </div>
    </AppShell>
  );
}

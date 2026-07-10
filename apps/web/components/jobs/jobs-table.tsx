"use client";

import { useCallback, useState } from "react";
import { ArrowDownUp, ExternalLink, Eye } from "lucide-react";

import { ApplicationStatusSelect } from "@/components/jobs/application-status-select";
import { MatchScoreBadge } from "@/components/jobs/match-score-badge";
import { VisaSignalBadge } from "@/components/jobs/visa-signal-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { formatCurrency, formatDate, formatNullable } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import type { Job, SortOrder } from "@/lib/types";

interface ResponsiveJobsTableProps {
  jobs: Job[];
  total: number;
  page: number;
  pageSize: number;
  sortBy: string;
  sortOrder: SortOrder;
  onSortChange: (sortBy: string, sortOrder: SortOrder) => void;
  onPageChange: (page: number) => void;
  onSelectJob: (job: Job) => void;
  onStatusChange: (job: Job, status: string) => Promise<void>;
}

const columns = [
  { label: "Score", width: "w-[6%]", sort: "match_score" },
  { label: "Role", width: "w-[18%]", sort: "job_title" },
  { label: "Company", width: "w-[9%]", sort: "company" },
  { label: "Category", width: "w-[9%]", sort: "category_name" },
  { label: "Industry", width: "w-[7%]" },
  { label: "Location", width: "w-[9%]" },
  { label: "Work", width: "w-[6%]" },
  { label: "Salary", width: "w-[8%]", sort: "salary_midpoint" },
  { label: "Visa", width: "w-[6%]" },
  { label: "Status", width: "w-[9%]" },
  { label: "Posted", width: "w-[7%]", sort: "date_posted" },
  { label: "Actions", width: "w-[6%]" }
];

function SortableHeader({
  label,
  column,
  active,
  onSort
}: {
  label: string;
  column?: string;
  active?: boolean;
  onSort: (column: string) => void;
}) {
  if (!column) {
    return <span>{label}</span>;
  }

  return (
    <button
      className={cn(
        "inline-flex max-w-full items-center gap-1 text-left",
        active ? "text-foreground" : "text-muted-foreground"
      )}
      type="button"
      onClick={() => onSort(column)}
    >
      <span className="truncate">{label}</span>
      <ArrowDownUp className="h-3 w-3 shrink-0" />
    </button>
  );
}

function TruncatedText({
  value,
  className
}: {
  value?: string | number | boolean | null;
  className?: string;
}) {
  const label = formatNullable(value);
  return (
    <span className={cn("block truncate", className)} title={label}>
      {label}
    </span>
  );
}

function WorkBadge({ value }: { value?: string | null }) {
  return (
    <span className="badge max-w-full truncate border-sky-200 bg-sky-50 text-sky-800" title={formatNullable(value)}>
      {formatNullable(value)}
    </span>
  );
}

function ActionButtons({ job, onSelectJob }: { job: Job; onSelectJob: (job: Job) => void }) {
  return (
    <div className="flex items-center gap-1.5">
      <button
        className="btn h-8 w-8 p-0"
        title="View details"
        type="button"
        onClick={() => onSelectJob(job)}
      >
        <Eye className="h-3.5 w-3.5" />
        <span className="sr-only">View details</span>
      </button>
      {job.jd_post_link ? (
        <a
          className="btn h-8 w-8 p-0"
          href={job.jd_post_link}
          rel="noreferrer"
          target="_blank"
          title="Open job description"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          <span className="sr-only">Open job description</span>
        </a>
      ) : null}
      {job.apply_link ? (
        <a
          className="btn btn-primary h-8 w-8 p-0"
          href={job.apply_link}
          rel="noreferrer"
          target="_blank"
          title="Open application"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          <span className="sr-only">Open application</span>
        </a>
      ) : null}
    </div>
  );
}

function JobField({
  label,
  value
}: {
  label: string;
  value?: string | number | boolean | null;
}) {
  return (
    <div className="min-w-0">
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <TruncatedText className="mt-1 text-sm text-foreground" value={value} />
    </div>
  );
}

export function ResponsiveJobsTable({
  jobs,
  total,
  page,
  pageSize,
  sortBy,
  sortOrder,
  onSortChange,
  onPageChange,
  onSelectJob,
  onStatusChange
}: ResponsiveJobsTableProps) {
  const [updatingJobId, setUpdatingJobId] = useState<string | null>(null);
  const pageCount = Math.max(Math.ceil(total / pageSize), 1);

  const requestSort = useCallback((column: string) => {
    const nextOrder: SortOrder = sortBy === column && sortOrder === "desc" ? "asc" : "desc";
    onSortChange(column, nextOrder);
  }, [onSortChange, sortBy, sortOrder]);

  const updateStatus = useCallback(async (job: Job, status: string) => {
    setUpdatingJobId(job.job_id);
    try {
      await onStatusChange(job, status);
    } finally {
      setUpdatingJobId(null);
    }
  }, [onStatusChange]);

  if (!jobs.length) {
    return <EmptyState title="No jobs match these filters" />;
  }

  return (
    <div className="space-y-3">
      <div className="hidden xl:block">
        <div className="table-shell">
          <table className="data-table table-fixed">
            <colgroup>
              {columns.map((column) => (
                <col key={column.label} className={column.width} />
              ))}
            </colgroup>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.label}>
                    <SortableHeader
                      active={sortBy === column.sort}
                      column={column.sort}
                      label={column.label}
                      onSort={requestSort}
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id} className="hover:bg-muted/40">
                  <td>
                    <MatchScoreBadge compact score={job.match_score} tier={job.match_tier} />
                  </td>
                  <td className="max-w-0">
                    <button
                      className="block max-w-full truncate text-left font-semibold text-foreground hover:text-primary"
                      title={formatNullable(job.job_title)}
                      type="button"
                      onClick={() => onSelectJob(job)}
                    >
                      {formatNullable(job.job_title)}
                    </button>
                  </td>
                  <td className="max-w-0">
                    <TruncatedText value={job.company} />
                  </td>
                  <td className="max-w-0">
                    <TruncatedText className="text-xs text-muted-foreground" value={job.category_name} />
                  </td>
                  <td className="max-w-0">
                    <TruncatedText value={job.industry} />
                  </td>
                  <td className="max-w-0">
                    <TruncatedText value={job.location} />
                  </td>
                  <td>
                    <WorkBadge value={job.work_arrangement} />
                  </td>
                  <td className="whitespace-nowrap">{formatCurrency(job.salary_midpoint)}</td>
                  <td>
                    <VisaSignalBadge signal={job.visa_signal} />
                  </td>
                  <td>
                    <ApplicationStatusSelect
                      className="w-full min-w-0 px-2"
                      disabled={updatingJobId === job.job_id}
                      value={job.application_status}
                      onChange={(value) => updateStatus(job, value)}
                    />
                  </td>
                  <td className="whitespace-nowrap">{formatDate(job.date_posted)}</td>
                  <td>
                    <ActionButtons job={job} onSelectJob={onSelectJob} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-3 xl:hidden">
        {jobs.map((job) => (
          <article key={job.job_id} className="rounded-lg border border-border bg-card p-4 shadow-soft">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap gap-2">
                  <MatchScoreBadge compact score={job.match_score} tier={job.match_tier} />
                  <VisaSignalBadge signal={job.visa_signal} />
                  <WorkBadge value={job.work_arrangement} />
                </div>
                <button
                  className="mt-3 block max-w-full truncate text-left text-base font-semibold text-foreground hover:text-primary"
                  title={formatNullable(job.job_title)}
                  type="button"
                  onClick={() => onSelectJob(job)}
                >
                  {formatNullable(job.job_title)}
                </button>
                <p className="mt-1 truncate text-sm text-muted-foreground" title={formatNullable(job.company)}>
                  {formatNullable(job.company)}
                </p>
              </div>
              <ActionButtons job={job} onSelectJob={onSelectJob} />
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <JobField label="Category" value={job.category_name} />
              <JobField label="Industry" value={job.industry} />
              <JobField label="Location" value={job.location} />
              <JobField label="Salary" value={formatCurrency(job.salary_midpoint)} />
              <JobField label="Posted" value={formatDate(job.date_posted)} />
              <div>
                <div className="text-xs font-semibold uppercase text-muted-foreground">Status</div>
                <ApplicationStatusSelect
                  className="mt-1 w-full"
                  disabled={updatingJobId === job.job_id}
                  value={job.application_status}
                  onChange={(value) => updateStatus(job, value)}
                />
              </div>
            </div>
          </article>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
        <div>
          Showing page {page} of {pageCount} ({total} jobs)
        </div>
        <div className="flex gap-2">
          <button className="btn" disabled={page <= 1} type="button" onClick={() => onPageChange(page - 1)}>
            Previous
          </button>
          <button
            className="btn"
            disabled={page >= pageCount}
            type="button"
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

export const JobsTable = ResponsiveJobsTable;

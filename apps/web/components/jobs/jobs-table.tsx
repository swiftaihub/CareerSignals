"use client";

import { useCallback, useMemo, useState } from "react";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable
} from "@tanstack/react-table";
import { ArrowDownUp, Eye } from "lucide-react";

import { ApplicationStatusSelect } from "@/components/jobs/application-status-select";
import { JobLinkButtons } from "@/components/jobs/job-link-buttons";
import { MatchScoreBadge } from "@/components/jobs/match-score-badge";
import { VisaSignalBadge } from "@/components/jobs/visa-signal-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { formatCurrency, formatDate, formatNullable } from "@/lib/formatters";
import type { Job, SortOrder } from "@/lib/types";

interface JobsTableProps {
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

function HeaderButton({
  label,
  column,
  onSort
}: {
  label: string;
  column: string;
  onSort: (column: string) => void;
}) {
  return (
    <button className="inline-flex items-center gap-1 text-left" type="button" onClick={() => onSort(column)}>
      {label}
      <ArrowDownUp className="h-3 w-3" />
    </button>
  );
}

export function JobsTable({
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
}: JobsTableProps) {
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

  const columns = useMemo<ColumnDef<Job>[]>(
    () => [
      {
        id: "match_score",
        header: () => <HeaderButton label="Score" column="match_score" onSort={requestSort} />,
        cell: ({ row }) => (
          <MatchScoreBadge score={row.original.match_score} tier={row.original.match_tier} />
        )
      },
      {
        id: "job_title",
        header: () => <HeaderButton label="Role" column="job_title" onSort={requestSort} />,
        cell: ({ row }) => (
          <button
            className="text-left font-semibold text-foreground hover:text-primary"
            type="button"
            onClick={() => onSelectJob(row.original)}
          >
            {formatNullable(row.original.job_title)}
          </button>
        )
      },
      {
        id: "company",
        header: () => <HeaderButton label="Company" column="company" onSort={requestSort} />,
        cell: ({ row }) => formatNullable(row.original.company)
      },
      {
        id: "category_name",
        header: () => <HeaderButton label="Category" column="category_name" onSort={requestSort} />,
        cell: ({ row }) => (
          <span className="text-xs text-muted-foreground">{formatNullable(row.original.category_name)}</span>
        )
      },
      {
        id: "industry",
        header: "Industry",
        cell: ({ row }) => formatNullable(row.original.industry)
      },
      {
        id: "location",
        header: "Location",
        cell: ({ row }) => formatNullable(row.original.location)
      },
      {
        id: "work_arrangement",
        header: "Work",
        cell: ({ row }) => formatNullable(row.original.work_arrangement)
      },
      {
        id: "salary_midpoint",
        header: () => <HeaderButton label="Salary" column="salary_midpoint" onSort={requestSort} />,
        cell: ({ row }) => formatCurrency(row.original.salary_midpoint)
      },
      {
        id: "visa_signal",
        header: "Visa",
        cell: ({ row }) => <VisaSignalBadge signal={row.original.visa_signal} />
      },
      {
        id: "application_status",
        header: "Status",
        cell: ({ row }) => (
          <ApplicationStatusSelect
            disabled={updatingJobId === row.original.job_id}
            value={row.original.application_status}
            onChange={(value) => updateStatus(row.original, value)}
          />
        )
      },
      {
        id: "date_posted",
        header: () => <HeaderButton label="Posted" column="date_posted" onSort={requestSort} />,
        cell: ({ row }) => formatDate(row.original.date_posted)
      },
      {
        id: "source",
        header: "Source",
        cell: ({ row }) => formatNullable(row.original.source)
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => (
          <div className="flex min-w-32 flex-wrap items-center gap-2">
            <button className="btn h-8 px-3 text-xs" type="button" onClick={() => onSelectJob(row.original)}>
              <Eye className="h-3.5 w-3.5" />
              Details
            </button>
            <JobLinkButtons job={row.original} />
          </div>
        )
      }
    ],
    [onSelectJob, requestSort, updateStatus, updatingJobId]
  );

  const table = useReactTable({
    data: jobs,
    columns,
    getCoreRowModel: getCoreRowModel()
  });

  if (!jobs.length) {
    return <EmptyState title="No jobs match these filters" />;
  }

  return (
    <div className="space-y-3">
      <div className="table-shell overflow-x-auto">
        <table className="data-table min-w-[1280px]">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.original.job_id} className="hover:bg-muted/40">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
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

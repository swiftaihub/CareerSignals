"use client";

import { useEffect, useMemo, useState } from "react";
import { Building2, CircleDollarSign, Star, UsersRound } from "lucide-react";

import { MetricCard } from "@/components/dashboard/metric-card";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { SectionCard } from "@/components/shared/section-card";
import { getCompanyPriority } from "@/lib/api";
import { formatCurrency, formatNullable, formatScore } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import type { ApiError, CompanyPriorityRow } from "@/lib/types";

const sortOptions = [
  { value: "highest_match_score", label: "Highest match score" },
  { value: "average_match_score", label: "Average match score" },
  { value: "matching_roles_count", label: "Matching roles count" },
  { value: "average_salary_midpoint", label: "Average salary" },
  { value: "priority", label: "Priority" }
];

function priorityClass(priority?: string | null) {
  if (priority === "High") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (priority === "Medium") {
    return "border-cyan-200 bg-cyan-50 text-cyan-800";
  }
  return "border-neutral-200 bg-neutral-100 text-neutral-700";
}

function priorityRank(priority?: string | null) {
  return priority === "High" ? 3 : priority === "Medium" ? 2 : 1;
}

export default function CompaniesPage() {
  const [rows, setRows] = useState<CompanyPriorityRow[]>([]);
  const [sortBy, setSortBy] = useState("priority");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  useEffect(() => {
    getCompanyPriority()
      .then(setRows)
      .catch((requestError) => setError(requestError as ApiError))
      .finally(() => setLoading(false));
  }, []);

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      if (sortBy === "priority") {
        return priorityRank(b.priority) - priorityRank(a.priority);
      }
      const left = Number(a[sortBy as keyof CompanyPriorityRow] || 0);
      const right = Number(b[sortBy as keyof CompanyPriorityRow] || 0);
      return right - left;
    });
  }, [rows, sortBy]);

  const summary = useMemo(() => {
    const highPriority = rows.filter((row) => row.priority === "High").length;
    const totalRoles = rows.reduce((sum, row) => sum + Number(row.matching_roles_count || 0), 0);
    const bestScore = Math.max(0, ...rows.map((row) => Number(row.highest_match_score || 0)));
    const averageSalaryValues = rows
      .map((row) => row.average_salary_midpoint)
      .filter((value): value is number => typeof value === "number");
    const avgSalary = averageSalaryValues.length
      ? averageSalaryValues.reduce((sum, value) => sum + value, 0) / averageSalaryValues.length
      : null;
    return { highPriority, totalRoles, bestScore, avgSalary };
  }, [rows]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Companies"
        title="Company priority analysis"
        description="Compare opportunity quality by company across role count, match scores, salary midpoint, visa signals, and priority tier."
      />

      {error ? <ErrorState error={error} /> : null}
      {loading ? <LoadingState label="Loading company priorities..." /> : null}

      {!loading && rows.length ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard icon={<Building2 className="h-5 w-5" />} label="Companies" value={rows.length} />
            <MetricCard icon={<Star className="h-5 w-5" />} label="High Priority" value={summary.highPriority} />
            <MetricCard icon={<UsersRound className="h-5 w-5" />} label="Matching Roles" value={summary.totalRoles} />
            <MetricCard icon={<CircleDollarSign className="h-5 w-5" />} label="Avg Salary" value={formatCurrency(summary.avgSalary)} />
          </div>

          <SectionCard
            className="mt-6"
            title="Priority List"
            action={
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                Sort
                <select className="select h-9 w-56" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
                  {sortOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            }
          >
            <div className="table-shell overflow-x-auto">
              <table className="data-table min-w-[980px]">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Industry</th>
                    <th>Roles</th>
                    <th>Avg Score</th>
                    <th>Highest Score</th>
                    <th>Avg Salary</th>
                    <th>Best Role</th>
                    <th>Visa Signal</th>
                    <th>Priority</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row) => (
                    <tr key={row.company}>
                      <td className="font-semibold">{row.company}</td>
                      <td>{formatNullable(row.industry)}</td>
                      <td>{row.matching_roles_count || 0}</td>
                      <td>{formatScore(row.average_match_score)}</td>
                      <td>{formatScore(row.highest_match_score)}</td>
                      <td>{formatCurrency(row.average_salary_midpoint)}</td>
                      <td>{formatNullable(row.best_matching_role)}</td>
                      <td className="max-w-xs text-muted-foreground">{formatNullable(row.visa_signal_summary)}</td>
                      <td>
                        <span className={cn("badge", priorityClass(row.priority))}>{formatNullable(row.priority)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      ) : null}

      {!loading && !rows.length ? <EmptyState title="No company priorities yet" /> : null}
    </AppShell>
  );
}

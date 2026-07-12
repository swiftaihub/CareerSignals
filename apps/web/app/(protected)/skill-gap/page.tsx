"use client";

import { useEffect, useMemo, useState } from "react";
import { Brain, CheckCircle2, Flame, ListChecks } from "lucide-react";

import { MetricCard } from "@/components/dashboard/metric-card";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { SectionCard } from "@/components/shared/section-card";
import { getSkillGap } from "@/lib/api";
import { formatNullable, formatPercent } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import type { ApiError, SkillGapRow } from "@/lib/types";

function priorityClass(priority?: string | null, covered?: string | boolean | null) {
  if (covered === true || covered === "Yes") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (priority === "High") {
    return "border-red-200 bg-red-50 text-red-800";
  }
  if (priority === "Medium") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-neutral-200 bg-neutral-100 text-neutral-700";
}

export default function SkillGapPage() {
  const [rows, setRows] = useState<SkillGapRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);

  useEffect(() => {
    getSkillGap()
      .then(setRows)
      .catch((requestError) => setError(requestError as ApiError))
      .finally(() => setLoading(false));
  }, []);

  const summary = useMemo(() => {
    const highPriority = rows.filter((row) => row.gap_priority === "High" && row.in_candidate_profile !== "Yes").length;
    const covered = rows.filter((row) => row.in_candidate_profile === "Yes" || row.in_candidate_profile === true).length;
    const mostFrequent = rows[0]?.skill || "Unknown";
    return { highPriority, covered, mostFrequent, total: rows.length };
  }, [rows]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Skill Gap"
        title="Market skills compared with your profile"
        description="Find frequent skills in target roles, separate already-covered capabilities from gaps, and decide what to improve next."
      />

      {error ? <ErrorState error={error} /> : null}
      {loading ? <LoadingState label="Loading skill gap analysis..." /> : null}

      {!loading && rows.length ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard icon={<Flame className="h-5 w-5" />} label="High Priority Gaps" value={summary.highPriority} />
            <MetricCard icon={<CheckCircle2 className="h-5 w-5" />} label="Skills Already Covered" value={summary.covered} />
            <MetricCard icon={<Brain className="h-5 w-5" />} label="Most Frequent Skill" value={summary.mostFrequent} />
            <MetricCard icon={<ListChecks className="h-5 w-5" />} label="Total Skills Detected" value={summary.total} />
          </div>

          <SectionCard className="mt-6" title="Skill Demand">
            <div className="table-shell overflow-x-auto">
              <table className="data-table min-w-[920px]">
                <thead>
                  <tr>
                    <th>Skill</th>
                    <th>Skill Group</th>
                    <th>Job Count</th>
                    <th>Job %</th>
                    <th>In Profile</th>
                    <th>Gap Priority</th>
                    <th>Example Titles</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.skill}-${row.skill_group}`}>
                      <td className="font-semibold">{row.skill}</td>
                      <td>{formatNullable(row.skill_group)}</td>
                      <td>{row.appears_in_job_count || 0}</td>
                      <td>{formatPercent(row.appears_in_job_pct)}</td>
                      <td>{formatNullable(row.in_candidate_profile)}</td>
                      <td>
                        <span className={cn("badge", priorityClass(row.gap_priority, row.in_candidate_profile))}>
                          {row.in_candidate_profile === "Yes" || row.in_candidate_profile === true
                            ? "Already covered"
                            : `${formatNullable(row.gap_priority)} priority`}
                        </span>
                      </td>
                      <td className="max-w-md text-muted-foreground">{formatNullable(row.example_matching_job_titles)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      ) : null}

      {!loading && !rows.length ? <EmptyState title="No skills detected yet" /> : null}
    </AppShell>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BriefcaseBusiness, CircleDollarSign, Gauge, RadioTower } from "lucide-react";

import { CategoryChart } from "@/components/dashboard/category-chart";
import { MatchTierChart } from "@/components/dashboard/match-tier-chart";
import { MetricCard } from "@/components/dashboard/metric-card";
import { VisaChart } from "@/components/dashboard/visa-chart";
import { WorkArrangementChart } from "@/components/dashboard/work-arrangement-chart";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { MatchScoreBadge } from "@/components/jobs/match-score-badge";
import { VisaSignalBadge } from "@/components/jobs/visa-signal-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { SectionCard } from "@/components/shared/section-card";
import { getDashboardSummary } from "@/lib/api";
import { formatCurrency, formatDate, formatNullable, formatScore } from "@/lib/formatters";
import type { ApiError, DashboardSummary } from "@/lib/types";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardSummary()
      .then(setSummary)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <AppShell>
        <LoadingState />
      </AppShell>
    );
  }

  if (error || !summary) {
    return (
      <AppShell>
        <ErrorState error={error} />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Dashboard"
        title="Career intelligence command center"
        description="Monitor data freshness, market signal quality, top matches, and role-fit distribution from one FastAPI-backed view."
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          helper="All roles available in the active intelligence dataset"
          icon={<BriefcaseBusiness className="h-5 w-5" />}
          label="Total Jobs"
          value={summary.metrics.total_jobs}
        />
        <MetricCard
          helper="Roles scoring 80 or higher"
          icon={<Gauge className="h-5 w-5" />}
          label="Top Matches"
          value={summary.metrics.top_matches}
        />
        <MetricCard
          helper="Average normalized role-fit score"
          label="Average Match Score"
          value={formatScore(summary.metrics.average_match_score)}
        />
        <MetricCard
          helper="Average salary midpoint where available"
          icon={<CircleDollarSign className="h-5 w-5" />}
          label="Average Salary"
          value={formatCurrency(summary.metrics.average_salary_midpoint)}
        />
        <MetricCard
          helper="Remote or hybrid roles"
          label="Remote / Hybrid"
          value={summary.metrics.remote_or_hybrid_roles}
        />
        <MetricCard
          helper="Positive or unknown sponsorship signal"
          label="Positive / Unknown Visa"
          value={summary.metrics.positive_or_unknown_visa_roles}
        />
        <MetricCard
          helper="Latest API or ingestion timestamp"
          icon={<RadioTower className="h-5 w-5" />}
          label="Latest Pipeline Run"
          value={formatDate(summary.data_status.last_pipeline_run_at || summary.data_status.last_pipeline_run)}
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <SectionCard title="Jobs by Category">
          <CategoryChart data={summary.category_summary} />
        </SectionCard>
        <SectionCard title="Visa Signal Distribution">
          <VisaChart data={summary.visa_signal_distribution} />
        </SectionCard>
        <SectionCard title="Work Arrangement Distribution">
          <WorkArrangementChart data={summary.work_arrangement_distribution} />
        </SectionCard>
        <SectionCard title="Match Tier Distribution">
          <MatchTierChart data={summary.match_tier_distribution} />
        </SectionCard>
      </div>

      <SectionCard
        className="mt-6"
        title="Latest Top Matches"
        description="Roles most worth reviewing first based on match score and priority signals."
        action={<Link className="btn" href="/top-matches">View All</Link>}
      >
        {!summary.top_matches_preview.length ? (
          <EmptyState title="No top matches yet" />
        ) : (
          <div className="table-shell overflow-x-auto">
            <table className="data-table min-w-[760px]">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Company</th>
                  <th>Score</th>
                  <th>Salary</th>
                  <th>Visa</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {summary.top_matches_preview.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <div className="font-semibold">{formatNullable(job.job_title)}</div>
                      <div className="text-xs text-muted-foreground">{formatNullable(job.location)}</div>
                    </td>
                    <td>{formatNullable(job.company)}</td>
                    <td><MatchScoreBadge score={job.match_score} tier={job.match_tier} /></td>
                    <td>{formatCurrency(job.salary_midpoint)}</td>
                    <td>
                      <VisaSignalBadge
                        confidence={job.visa_confidence}
                        evidence={job.visa_evidence}
                        signal={job.visa_signal}
                        status={job.visa_status}
                      />
                    </td>
                    <td><Link className="btn h-8 px-3 text-xs" href="/jobs">Open Jobs</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <div className="mt-6 flex flex-wrap gap-3">
        {[
          ["/jobs", "Explore All Jobs"],
          ["/top-matches", "View Top Matches"],
          ["/skill-gap", "Skill Gap"],
          ["/companies", "Company Priority"],
          ["/settings", "Settings"]
        ].map(([href, label]) => (
          <Link key={href} className="btn" href={href}>
            {label}
          </Link>
        ))}
      </div>
    </AppShell>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Activity, CircleDollarSign, Gauge, Users } from "lucide-react";

import { AdminDateFilter, type AdminDateRange } from "@/components/admin/date-filter";
import { GlobalRefreshControl } from "@/components/admin/global-refresh-control";
import { KpiCard } from "@/components/admin/kpi-card";
import { AdminTrendChart } from "@/components/admin/trend-chart";
import { DistributionChart } from "@/components/dashboard/distribution-chart";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { SectionCard } from "@/components/shared/section-card";
import { getAdminMetrics } from "@/lib/api-client";
import type { AdminMetrics } from "@/lib/types";

const today = new Date();
const thirtyDaysAgo = new Date(today.getTime() - 29 * 86400000);
const initialRange = {
  start_date: thirtyDaysAgo.toISOString().slice(0, 10),
  end_date: today.toISOString().slice(0, 10)
};

const money = (cents: number) =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format((cents || 0) / 100);

export function AdminOverview() {
  const [range, setRange] = useState<AdminDateRange>(initialRange);
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getAdminMetrics({
      ...range,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
    })
      .then(setMetrics)
      .catch((requestError) =>
        setError(
          requestError instanceof Error
            ? requestError
            : new Error("Admin metrics unavailable.")
        )
      )
      .finally(() => setLoading(false));
  }, [range]);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase text-primary">Administration</div>
          <h1 className="mt-2 text-3xl font-bold">Platform overview</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Account, engagement, Pipeline, and revenue-placeholder metrics.
          </p>
        </div>
        <AdminDateFilter value={range} onChange={setRange} />
      </div>

      <GlobalRefreshControl />

      {loading ? <LoadingState label="Loading Admin metrics..." /> : null}
      {error ? <ErrorState error={error} /> : null}

      {metrics ? (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard icon={<Users className="h-5 w-5" />} label="Registered Users" value={metrics.total_registered_users} />
            <KpiCard label="New Users" value={metrics.new_registered_users} />
            <KpiCard label="Pending" value={metrics.pending_users} />
            <KpiCard label="Active" value={metrics.active_users} />
            <KpiCard label="Expired" value={metrics.expired_users} />
            <KpiCard icon={<CircleDollarSign className="h-5 w-5" />} label="Estimated MRR" value={money(metrics.estimated_mrr_cents)} helper="Active non-Demo users x $5; not actual revenue." />
            <KpiCard label="Actual Monthly Revenue" value={money(metrics.actual_monthly_revenue_cents)} />
            <KpiCard label="Total Actual Revenue" value={money(metrics.total_revenue_cents)} />
            <KpiCard icon={<Gauge className="h-5 w-5" />} label="Pipeline Success" value={`${Math.round((metrics.pipeline_success_rate || 0) * (metrics.pipeline_success_rate <= 1 ? 100 : 1))}%`} />
            <KpiCard icon={<Activity className="h-5 w-5" />} label="Avg Pipeline Duration" value={`${Math.round(metrics.average_pipeline_duration_seconds || 0)}s`} />
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-2">
            <SectionCard title="Registrations over time">
              <AdminTrendChart data={metrics.registrations_by_day} />
            </SectionCard>
            <SectionCard title="Active users over time">
              <AdminTrendChart data={metrics.active_users_by_day} color="#2563eb" />
            </SectionCard>
            <SectionCard title="Activity by hour">
              <AdminTrendChart data={metrics.activity_by_hour} color="#7c3aed" />
            </SectionCard>
            <SectionCard title="Account status distribution">
              <DistributionChart
                data={[
                  { label: "Pending", count: metrics.pending_users },
                  { label: "Active", count: metrics.active_users },
                  { label: "Expired", count: metrics.expired_users },
                  { label: "Suspended", count: metrics.suspended_users || 0 }
                ]}
              />
            </SectionCard>
            <SectionCard title="Pipeline runs and failures">
              <AdminTrendChart data={metrics.pipeline_runs_by_day} color="#dc2626" />
            </SectionCard>
            <SectionCard title="Revenue events">
              <AdminTrendChart data={metrics.revenue_events_by_day} color="#059669" />
            </SectionCard>
            <SectionCard title="Expiration outlook">
              <AdminTrendChart data={metrics.expiration_outlook} color="#d97706" />
            </SectionCard>
          </div>
        </>
      ) : null}
    </>
  );
}

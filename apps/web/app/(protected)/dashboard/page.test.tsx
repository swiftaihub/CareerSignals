// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DashboardSummary } from "@/lib/types";
import { getDashboardSummary } from "@/lib/api-client";
import DashboardPage from "./page";

vi.mock("@/lib/api-client", () => ({
  getDashboardSummary: vi.fn()
}));

vi.mock("@/components/layout/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main>
}));

vi.mock("@/components/dashboard/category-chart", () => ({
  CategoryChart: () => <div>Category chart</div>
}));
vi.mock("@/components/dashboard/visa-chart", () => ({
  VisaChart: () => <div>Visa chart</div>
}));
vi.mock("@/components/dashboard/work-arrangement-chart", () => ({
  WorkArrangementChart: () => <div>Work arrangement chart</div>
}));
vi.mock("@/components/dashboard/match-tier-chart", () => ({
  MatchTierChart: () => <div>Match tier chart</div>
}));
vi.mock("@/components/dashboard/job-search-funnel", () => ({
  JobSearchFunnel: () => <div>Funnel visualization</div>
}));
vi.mock("@/components/dashboard/job-volume-trend-chart", () => ({
  JobVolumeTrendChart: () => <div>Volume visualization</div>
}));

const SUMMARY: DashboardSummary = {
  data_status: { last_pipeline_run_at: "2026-07-12T12:00:00Z" },
  metrics: {
    total_jobs: 318,
    top_matches: 12,
    average_match_score: 74,
    average_salary_midpoint: 125000,
    remote_or_hybrid_roles: 100,
    positive_or_unknown_visa_roles: 200
  },
  category_summary: [],
  top_matches_preview: [],
  visa_signal_distribution: [],
  work_arrangement_distribution: [],
  match_tier_distribution: [],
  funnel: {
    total_global_jobs: 2450,
    total_user_jobs: 318,
    total_applied_jobs: 27,
    total_interviews: 6
  },
  job_count_timeseries: [
    { date: "2026-07-12", global_jobs: 2450, user_jobs: 318, applied_jobs: 27 }
  ],
  analytics_window: {
    start_date: "2026-06-13",
    end_date: "2026-07-12",
    days: 30
  }
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("DashboardPage analytics", () => {
  it("uses the existing loading flow and preserves all dashboard sections", async () => {
    let resolveSummary: (value: DashboardSummary) => void = () => undefined;
    vi.mocked(getDashboardSummary).mockReturnValue(new Promise((resolve) => {
      resolveSummary = resolve;
    }));

    render(<DashboardPage />);
    expect(screen.getByText("Loading dashboard data...")).toBeInTheDocument();

    await act(async () => resolveSummary(SUMMARY));

    expect(getDashboardSummary).toHaveBeenCalledOnce();
    expect(getDashboardSummary).toHaveBeenCalledWith(30);
    for (const heading of [
      "Job Search Funnel",
      "Job Volume Over Time",
      "Jobs by Category",
      "Visa Signal Distribution",
      "Work Arrangement Distribution",
      "Match Tier Distribution",
      "Latest Top Matches"
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(screen.getByText("Total Jobs")).toBeInTheDocument();
    expect(screen.getByText("Funnel visualization")).toBeInTheDocument();
    expect(screen.getByText("Volume visualization")).toBeInTheDocument();
  });

  it("uses the existing API failure state", async () => {
    vi.mocked(getDashboardSummary).mockRejectedValue(new Error("Analytics unavailable"));
    render(<DashboardPage />);

    expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("Analytics unavailable")).toBeInTheDocument();
  });
});

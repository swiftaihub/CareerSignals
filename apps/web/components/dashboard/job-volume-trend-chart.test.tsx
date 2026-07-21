// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  JOB_VOLUME_SERIES,
  JobVolumeTooltip,
  JobVolumeTrendChart
} from "./job-volume-trend-chart";

afterEach(cleanup);

describe("JobVolumeTrendChart", () => {
  it("defines exactly the three required line series", () => {
    expect(JOB_VOLUME_SERIES.map((series) => [series.dataKey, series.name])).toEqual([
      ["global_jobs", "New Global Jobs"],
      ["user_jobs", "New Jobs for You"],
      ["applied_jobs", "New Applications"]
    ]);
  });

  it("renders a proper empty state for absent and all-null history", () => {
    const { rerender } = render(<JobVolumeTrendChart data={[]} />);
    expect(screen.getByText("No new-job history yet")).toBeInTheDocument();

    rerender(
      <JobVolumeTrendChart
        data={[{ date: "2026-07-12", global_jobs: null, user_jobs: null, applied_jobs: null }]}
      />
    );
    expect(screen.getByText("No new-job history yet")).toBeInTheDocument();
  });

  it("preserves the full ISO date and sparse values for one-point history", () => {
    render(
      <JobVolumeTrendChart
        data={[{ date: "2026-07-12", global_jobs: 2450, user_jobs: null, applied_jobs: 27 }]}
      />
    );

    expect(screen.getByRole("img", { name: /daily new-job line chart/i })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Daily new-job values" });
    expect(within(table).getByText("2026-07-12")).toBeInTheDocument();
    expect(within(table).getByText("2,450")).toBeInTheDocument();
    expect(within(table).getByText("27")).toBeInTheDocument();
    expect(within(table).getByText("Not available")).toBeInTheDocument();
  });

  it("treats missing runtime values as unavailable instead of fabricated zeros", () => {
    render(
      <JobVolumeTrendChart
        data={[{
          date: "2026-07-12",
          global_jobs: 2450,
          applied_jobs: null
        } as never]}
      />
    );

    const table = screen.getByRole("table", { name: "Daily new-job values" });
    expect(within(table).getAllByText("Not available")).toHaveLength(2);
    expect(within(table).queryByText("0")).not.toBeInTheDocument();
  });

  it("omits all-unknown days while preserving partial and known-zero days", () => {
    render(
      <JobVolumeTrendChart
        data={[
          { date: "2026-07-10", global_jobs: null, user_jobs: null, applied_jobs: null },
          { date: "2026-07-11", global_jobs: 120, user_jobs: null, applied_jobs: null },
          { date: "2026-07-12", global_jobs: 0, user_jobs: 0, applied_jobs: 0 }
        ]}
      />
    );

    const table = screen.getByRole("table", { name: "Daily new-job values" });
    expect(within(table).queryByText("2026-07-10")).not.toBeInTheDocument();
    expect(within(table).getByText("2026-07-11")).toBeInTheDocument();
    expect(within(table).getByText("2026-07-12")).toBeInTheDocument();
    expect(within(table).getAllByText("0")).toHaveLength(3);
  });

  it("shows the complete date and all three values in the custom tooltip", () => {
    render(
      <JobVolumeTooltip
        active
        date="2026-06-13"
        point={{ date: "2026-06-13", global_jobs: 2180, user_jobs: 281, applied_jobs: 19 }}
      />
    );

    expect(screen.getByText("2026-06-13")).toBeInTheDocument();
    expect(screen.getByText("2,180")).toBeInTheDocument();
    expect(screen.getByText("281")).toBeInTheDocument();
    expect(screen.getByText("19")).toBeInTheDocument();
    for (const label of ["New Global Jobs", "New Jobs for You", "New Applications"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});

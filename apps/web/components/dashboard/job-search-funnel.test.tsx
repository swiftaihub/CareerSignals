// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { buildFunnelStages, JobSearchFunnel } from "./job-search-funnel";

afterEach(cleanup);

const FUNNEL = {
  total_global_jobs: 2450,
  total_user_jobs: 318,
  total_applied_jobs: 27,
  total_interviews: 6
};

describe("JobSearchFunnel", () => {
  it("keeps the required stage order and calculates conversions from real counts", () => {
    const stages = buildFunnelStages(FUNNEL);

    expect(stages.map((stage) => stage.label)).toEqual([
      "Total Global Jobs",
      "Jobs for You",
      "Applied Jobs",
      "Interviews"
    ]);
    expect(stages[1]).toMatchObject({
      count: 318,
      previousCount: 2450,
      conversionFromPrevious: 318 / 2450,
      shareOfTotal: 318 / 2450,
      dropOffFromPrevious: 2132
    });
    expect(stages[3]).toMatchObject({
      conversionFromPrevious: 6 / 27,
      dropOffFromPrevious: 21
    });
  });

  it("renders and focuses zero-count stages instead of filtering them out", () => {
    render(
      <JobSearchFunnel
        data={{
          total_global_jobs: 10,
          total_user_jobs: 0,
          total_applied_jobs: 0,
          total_interviews: 0
        }}
      />
    );

    const interviews = screen.getByLabelText(/Interviews: 0 jobs/i);
    expect(interviews).toHaveAttribute("tabindex", "0");

    fireEvent.focus(interviews);
    const tooltip = screen.getByRole("tooltip");
    expect(within(tooltip).getByText("Interviews")).toBeInTheDocument();
    expect(within(tooltip).getByText("Not available")).toBeInTheDocument();
    expect(within(tooltip).getByText("0", { selector: "dd" })).toBeInTheDocument();
  });

  it("shows count, conversion, global share, and drop-off on hover", () => {
    render(<JobSearchFunnel data={FUNNEL} />);

    fireEvent.mouseEnter(screen.getByLabelText(/Applied Jobs: 27 jobs/i));

    const tooltip = screen.getByRole("tooltip");
    expect(within(tooltip).getByText("27")).toBeInTheDocument();
    expect(within(tooltip).getByText("8.5%")).toBeInTheDocument();
    expect(within(tooltip).getByText("1.1%")).toBeInTheDocument();
    expect(within(tooltip).getByText("291")).toBeInTheDocument();
  });

  it("keeps tiny nonzero stages readable and preserves keyboard focus across pointer movement", () => {
    render(
      <JobSearchFunnel
        data={{
          total_global_jobs: 100000,
          total_user_jobs: 250,
          total_applied_jobs: 2,
          total_interviews: 1
        }}
      />
    );

    const interviewStage = screen.getByLabelText(/Interviews: 1 jobs/i);
    fireEvent.focus(interviewStage);
    fireEvent.mouseEnter(interviewStage);
    fireEvent.mouseLeave(interviewStage);

    expect(interviewStage).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Interviews");
    expect(screen.getByText("1", { selector: "span" })).toBeInTheDocument();
  });
});

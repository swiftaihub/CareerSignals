// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AdminConnectorRunList } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  createAdminConnectorRun: vi.fn(),
  getAdminConnectorRuns: vi.fn()
}));

vi.mock("@/lib/api-client", () => mocks);

import { GlobalRefreshControl } from "./global-refresh-control";

describe("GlobalRefreshControl", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("polls while a refresh is active and displays its completion", async () => {
    const running: AdminConnectorRunList = {
      items: [{
        connector_run_uuid: "run-1",
        status: "running",
        trigger_type: "manual",
        created_at: "2026-07-17T22:00:00Z",
        public_status_message: "Refresh in progress."
      }]
    };
    const completed: AdminConnectorRunList = {
      items: [{ ...running.items[0], status: "completed", completed_at: "2026-07-17T22:05:00Z" }]
    };
    mocks.getAdminConnectorRuns.mockResolvedValueOnce(running).mockResolvedValueOnce(completed);

    await act(async () => {
      render(<GlobalRefreshControl />);
      await Promise.resolve();
    });
    expect(screen.getByText("Global Refresh Running")).toBeDisabled();
    expect(screen.getByText("Refresh in progress.")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(mocks.getAdminConnectorRuns).toHaveBeenCalledTimes(2);
    expect(screen.getByText("Manual Global Refresh")).toBeEnabled();
  });
});

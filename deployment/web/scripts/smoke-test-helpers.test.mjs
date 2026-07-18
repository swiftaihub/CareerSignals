import { describe, expect, it, vi } from "vitest";

import {
  containsDuplicateBasePath,
  containsMixedContent,
  requestWithRetry
} from "./smoke-test-helpers.mjs";

describe("containsMixedContent", () => {
  it("ignores non-fetching HTTP namespace declarations", () => {
    const body = '<svg xmlns="http://www.w3.org/2000/svg"><path /></svg>';

    expect(containsMixedContent(body)).toBe(false);
  });

  it.each([
    '<img src="http://assets.example.com/image.png">',
    '<a href="http://example.com">Example</a>',
    '<img srcset="https://example.com/a.png 1x, http://example.com/b.png 2x">',
    '<div style="background-image: url(http://example.com/image.png)"></div>'
  ])("detects mixed content in browser-fetching URLs", (body) => {
    expect(containsMixedContent(body)).toBe(true);
  });
});

describe("containsDuplicateBasePath", () => {
  it("detects a duplicated mounted route", () => {
    expect(containsDuplicateBasePath(
      '<a href="/careersignals/careersignals/dashboard">Dashboard</a>',
      "/careersignals"
    )).toBe(true);
  });

  it("does not mistake the CareerSignals icon filename for another path segment", () => {
    expect(containsDuplicateBasePath(
      '<link rel="icon" href="/careersignals/careersignals-icon.svg">',
      "/careersignals"
    )).toBe(false);
  });
});

describe("requestWithRetry", () => {
  it("retries a Cloudflare 522 with exponential backoff", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 522 }))
      .mockResolvedValueOnce(new Response(null, { status: 200 }));
    const sleep = vi.fn().mockResolvedValue(undefined);
    const onRetry = vi.fn();

    const response = await requestWithRetry("https://example.com/careersignals", {
      fetchImpl,
      maxAttempts: 3,
      retryDelayMs: 10,
      sleep,
      onRetry
    });

    expect(response.status).toBe(200);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(10);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("returns the final 522 after exhausting the retry budget", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 522 }));
    const sleep = vi.fn().mockResolvedValue(undefined);

    const response = await requestWithRetry("https://example.com/careersignals", {
      fetchImpl,
      maxAttempts: 3,
      retryDelayMs: 10,
      sleep,
      onRetry: vi.fn()
    });

    expect(response.status).toBe(522);
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(sleep.mock.calls).toEqual([[10], [20]]);
  });

  it("does not retry application errors", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 500 }));
    const sleep = vi.fn().mockResolvedValue(undefined);

    const response = await requestWithRetry("https://example.com/careersignals", {
      fetchImpl,
      sleep,
      onRetry: vi.fn()
    });

    expect(response.status).toBe(500);
    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(sleep).not.toHaveBeenCalled();
  });

  it("forwards an explicit request method and headers", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(null, { status: 303 }));

    await requestWithRetry("https://example.com/careersignals/auth/logout", {
      fetchImpl,
      requestInit: {
        method: "POST",
        headers: { origin: "https://example.com" }
      }
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://example.com/careersignals/auth/logout",
      expect.objectContaining({
        method: "POST",
        redirect: "manual",
        headers: expect.objectContaining({
          origin: "https://example.com",
          "user-agent": "CareerSignals deployment smoke test"
        })
      })
    );
  });
});

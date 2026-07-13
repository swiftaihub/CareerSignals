import { NextResponse, type NextRequest } from "next/server";

import { getServerAuthorization } from "@/lib/auth";
import {
  backendPathFromSegments,
  safeBackendRedirectLocation
} from "@/lib/backend-policy";
import { getBackendBaseUrl } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, context: RouteContext) {
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
    const origin = request.headers.get("origin");
    if (origin && origin !== request.nextUrl.origin) {
      return NextResponse.json(
        { detail: "Cross-origin mutations are not allowed.", error_code: "CSRF_CHECK_FAILED" },
        { status: 403 }
      );
    }
  }

  const segments = (await context.params).path || [];
  const encodedPath = backendPathFromSegments(segments);
  if (!encodedPath) {
    return NextResponse.json(
      { detail: "This backend operation is not available.", error_code: "OPERATION_NOT_ALLOWED" },
      { status: 404 }
    );
  }

  let backendBaseUrl: string;
  try {
    backendBaseUrl = getBackendBaseUrl();
  } catch {
    return NextResponse.json(
      { detail: "The CareerSignals service is not configured.", error_code: "API_NOT_CONFIGURED" },
      { status: 503 }
    );
  }
  const target = new URL(`${backendBaseUrl}${encodedPath}`);
  request.nextUrl.searchParams.forEach((value, key) => target.searchParams.append(key, value));

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", request.headers.get("accept") || "application/json");

  const authorization = await getServerAuthorization();
  if (authorization) headers.set("authorization", authorization);

  const requestId = request.headers.get("x-request-id");
  if (requestId) headers.set("x-request-id", requestId);

  const body = request.method === "GET" || request.method === "HEAD"
    ? undefined
    : await request.arrayBuffer();

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual"
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "content-disposition", "cache-control", "x-request-id"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }

    if (upstream.status >= 300 && upstream.status < 400 && upstream.status !== 304) {
      const location = safeBackendRedirectLocation(
        upstream.headers.get("location"),
        backendBaseUrl
      );
      if (!location) {
        return NextResponse.json(
          {
            detail: "The backend returned an unsafe redirect.",
            error_code: "UPSTREAM_REDIRECT_REJECTED"
          },
          { status: 502 }
        );
      }
      responseHeaders.set("location", location);
    }

    // Backend cookies are never browser session state. Relaying Set-Cookie
    // could create host-wide or unscoped cookies, so the BFF intentionally
    // drops them.

    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders
    });
  } catch {
    return NextResponse.json(
      { detail: "The CareerSignals service is temporarily unavailable.", error_code: "API_UNREACHABLE" },
      { status: 503 }
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;

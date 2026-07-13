const ALLOWED_BACKEND_PATHS = [
  /^\/api\/health$/,
  /^\/api\/me$/,
  /^\/api\/configs(?:\/.*)?$/,
  /^\/api\/preferences(?:\/.*)?$/,
  /^\/api\/data-freshness$/,
  /^\/api\/pipeline-runs(?:\/.*)?$/,
  /^\/api\/jobs(?:\/.*)?$/,
  /^\/api\/(?:top-matches|category-summary|skill-gap|company-priority|dashboard\/summary)$/,
  /^\/api\/exports\/excel$/,
  /^\/api\/admin(?:\/.*)?$/
];

function isSafeSegment(segment: string) {
  return Boolean(segment)
    && segment !== "."
    && segment !== ".."
    && segment.length <= 256
    && !segment.includes("/")
    && !segment.includes("\\")
    && !/[\u0000-\u001f\u007f]/.test(segment);
}

export function backendPathFromSegments(segments: string[]) {
  if (!segments.length || !segments.every(isSafeSegment)) return null;
  const decodedPath = `/${segments.join("/")}`;
  if (!ALLOWED_BACKEND_PATHS.some((pattern) => pattern.test(decodedPath))) return null;
  return `/${segments.map((segment) => encodeURIComponent(segment)).join("/")}`;
}

/**
 * Rewrites a same-backend redirect through the authenticated same-origin BFF.
 * External or non-allowlisted redirects are rejected.
 */
export function safeBackendRedirectLocation(
  value: unknown,
  backendBaseUrl: string
) {
  if (
    typeof value !== "string"
    || !value
    || /[\\\u0000-\u001f\u007f]/.test(value)
    || /(?:^|\/)\.{1,2}(?:\/|$)|%(?:2e|2f|5c)/i.test(value)
  ) {
    return null;
  }

  try {
    const backend = new URL(backendBaseUrl);
    const destination = new URL(value, `${backend.origin}/`);
    if (
      destination.origin !== backend.origin
      || destination.username
      || destination.password
    ) {
      return null;
    }
    const segments = destination.pathname
      .split("/")
      .filter(Boolean)
      .map((segment) => decodeURIComponent(segment));
    const path = backendPathFromSegments(segments);
    if (!path) return null;
    return `${withBasePath(`/api/backend${path}`)}${destination.search}${destination.hash}`;
  } catch {
    return null;
  }
}
import { withBasePath } from "./app-path";

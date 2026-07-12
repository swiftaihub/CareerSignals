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

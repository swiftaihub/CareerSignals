const origin = (process.env.APP_ORIGIN || "https://jobs.swiftaihub.com").replace(/\/$/, "");
const basePath = normalizeBasePath(process.env.APP_BASE_PATH || "/careersignals");
const appUrl = `${origin}${basePath}`;
const requireHttpsAssets = new URL(origin).protocol === "https:";
const expectedSourceSha = process.env.EXPECTED_SOURCE_SHA?.trim() || "";
if (expectedSourceSha && !/^[0-9a-f]{40}$/.test(expectedSourceSha)) {
  fail("EXPECTED_SOURCE_SHA must be a full lowercase Git SHA");
}
const publicPaths = ["", "/login", "/register", "/pricing"];
const guardedPaths = [
  "/dashboard",
  "/jobs",
  "/top-matches",
  "/skill-gap",
  "/companies",
  "/settings",
  "/admin"
];

for (const path of publicPaths) {
  const response = await request(`${appUrl}${path}`);
  if (response.status < 200 || response.status >= 300) {
    fail(`${path || "/"} returned ${response.status}`);
  }
  const body = await response.text();
  if (requireHttpsAssets && /http:\/\//i.test(body)) fail(`${path || "/"} contains mixed-content HTTP URLs`);
  if (body.includes(`${basePath}${basePath}`)) fail(`${path || "/"} contains a duplicate base path`);
  if (/\b(?:href|src)=["']\/(?!careersignals(?:\/|["'#?]))/i.test(body)) {
    fail(`${path || "/"} contains an application-root URL outside the base path`);
  }
}

for (const path of guardedPaths) {
  const response = await request(`${appUrl}${path}`);
  if (response.status < 300 || response.status >= 400) {
    fail(`${path} must redirect an unauthenticated request; received ${response.status}`);
  }
  const location = response.headers.get("location");
  if (!location) fail(`${path} returned a redirect without Location`);
  const destination = assertInternalLocation(location, path);
  if (destination.pathname !== `${basePath}/login`) {
    fail(`${path} must redirect an unauthenticated request to ${basePath}/login`);
  }
}

const callback = await request(`${appUrl}/auth/callback`);
if (callback.status < 300 || callback.status >= 400) {
  fail(`/auth/callback without a code must redirect safely; received ${callback.status}`);
}
const callbackLocation = callback.headers.get("location");
if (!callbackLocation) fail("/auth/callback returned a redirect without Location");
const callbackDestination = assertInternalLocation(callbackLocation, "/auth/callback");
if (callbackDestination.pathname !== `${basePath}/forgot-password`) {
  fail(`/auth/callback without a code must redirect to ${basePath}/forgot-password`);
}

const health = await request(`${appUrl}/api/backend/api/health`);
if (!health.ok) fail(`same-origin BFF health returned ${health.status}`);
if (expectedSourceSha) {
  let payload;
  try {
    payload = await health.json();
  } catch {
    fail("same-origin BFF health did not return JSON");
  }
  if (payload?.status !== "ok" || payload?.source_commit_sha !== expectedSourceSha) {
    fail("same-origin BFF health did not report the expected canonical source SHA");
  }
}

console.log(`Production smoke tests passed for ${appUrl}.`);

async function request(url) {
  return fetch(url, {
    redirect: "manual",
    headers: { "user-agent": "CareerSignals deployment smoke test" }
  });
}

function assertInternalLocation(location, sourcePath) {
  const destination = new URL(location, origin);
  if (destination.origin !== origin || !isWithinBasePath(destination.pathname)) {
    fail(`${sourcePath} redirects outside ${basePath}`);
  }
  return destination;
}

function isWithinBasePath(pathname) {
  return pathname === basePath || pathname.startsWith(`${basePath}/`);
}

function normalizeBasePath(value) {
  const normalized = `/${value}`.replace(/\/{2,}/g, "/").replace(/\/$/, "");
  return normalized === "/" ? "" : normalized;
}

function fail(message) {
  console.error(`Smoke test failed: ${message}`);
  process.exit(1);
}

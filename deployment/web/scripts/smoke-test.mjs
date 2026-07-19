import {
  containsDuplicateBasePath,
  containsMixedContent,
  requestWithRetry
} from "./smoke-test-helpers.mjs";

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
  const response = await requestWithRetry(`${appUrl}${path}`);
  if (response.status < 200 || response.status >= 300) {
    fail(`${path || "/"} returned ${response.status}`);
  }
  const body = await response.text();
  if (requireHttpsAssets && containsMixedContent(body)) {
    fail(`${path || "/"} contains mixed-content HTTP URLs`);
  }
  if (containsDuplicateBasePath(body, basePath)) {
    fail(`${path || "/"} contains a duplicate base path`);
  }
  if (/\b(?:href|src)=["']\/(?!careersignals(?:\/|["'#?]))/i.test(body)) {
    fail(`${path || "/"} contains an application-root URL outside the base path`);
  }
}

for (const path of guardedPaths) {
  const response = await requestWithRetry(`${appUrl}${path}`);
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

const callback = await requestWithRetry(`${appUrl}/auth/callback`);
if (callback.status < 300 || callback.status >= 400) {
  fail(`/auth/callback without a code must redirect safely; received ${callback.status}`);
}
const callbackLocation = callback.headers.get("location");
if (!callbackLocation) fail("/auth/callback returned a redirect without Location");
const callbackDestination = assertInternalLocation(callbackLocation, "/auth/callback");
if (callbackDestination.pathname !== `${basePath}/forgot-password`) {
  fail(`/auth/callback without a code must redirect to ${basePath}/forgot-password`);
}

const health = await requestWithRetry(`${appUrl}/api/backend/api/health`);
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

const demoCookieNames = [
  "careersignals-demo-token-v2",
  "careersignals-demo-token"
];
const logout = await requestWithRetry(`${appUrl}/auth/logout`, {
  requestInit: {
    method: "POST",
    headers: {
      origin,
      cookie: demoCookieNames.map((name) => `${name}=smoke-test`).join("; ")
    }
  }
});
if (logout.status !== 303) fail(`logout returned ${logout.status} instead of 303`);
const logoutLocation = logout.headers.get("location");
if (!logoutLocation || new URL(logoutLocation, origin).pathname !== (basePath || "/")) {
  fail("logout did not redirect to the application home");
}
const logoutCookies = typeof logout.headers.getSetCookie === "function"
  ? logout.headers.getSetCookie()
  : [logout.headers.get("set-cookie") || ""];
for (const name of demoCookieNames) {
  const expiredAtAppPath = logoutCookies.some((cookie) => (
    cookie.startsWith(`${name}=`)
    && cookie.includes(`Path=${basePath || "/"};`)
    && (
      cookie.includes("Max-Age=0")
      || cookie.includes("Expires=Thu, 01 Jan 1970 00:00:00 GMT")
    )
  ));
  if (!expiredAtAppPath) {
    fail(`logout did not expire ${name} at ${basePath || "/"}`);
  }
}

console.log(`Production smoke tests passed for ${appUrl}.`);

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

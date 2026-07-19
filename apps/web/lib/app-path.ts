const INTERNAL_URL_ORIGIN = "https://careersignals.invalid";
const DEFAULT_REDIRECT_PATH = "/dashboard";

function hasUnsafeCharacters(value: string) {
  return /[\\\u0000-\u001f\u007f]/.test(value);
}

/**
 * Returns the trusted public origin used for absolute application URLs.
 * Paths belong in NEXT_PUBLIC_BASE_PATH and are rejected here so there is a
 * single canonical source for each URL component.
 */
export function getSiteOrigin(
  configured = process.env.NEXT_PUBLIC_SITE_ORIGIN,
  nodeEnv = process.env.NODE_ENV
) {
  const candidate = configured?.trim();
  if (!candidate || hasUnsafeCharacters(candidate)) {
    throw new Error("NEXT_PUBLIC_SITE_ORIGIN must be an absolute HTTP(S) origin.");
  }

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error("NEXT_PUBLIC_SITE_ORIGIN must be an absolute HTTP(S) origin.");
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_SITE_ORIGIN must use HTTP or HTTPS.");
  }
  if (parsed.username || parsed.password) {
    throw new Error("NEXT_PUBLIC_SITE_ORIGIN must not contain credentials.");
  }
  if (parsed.pathname !== "/" || parsed.search || parsed.hash) {
    throw new Error("NEXT_PUBLIC_SITE_ORIGIN must not contain a path, query, or fragment.");
  }
  const isLoopback = parsed.hostname === "localhost"
    || parsed.hostname === "127.0.0.1"
    || parsed.hostname === "[::1]";
  if (nodeEnv === "production" && parsed.protocol !== "https:" && !isLoopback) {
    throw new Error("NEXT_PUBLIC_SITE_ORIGIN must use HTTPS in production.");
  }

  return parsed.origin;
}

/** Returns a normalized Next.js basePath (empty string or `/segment`). */
export function getBasePath(configured = process.env.NEXT_PUBLIC_BASE_PATH) {
  const candidate = configured?.trim() ?? "";
  if (!candidate || candidate === "/") return "";
  if (
    !candidate.startsWith("/")
    || candidate.startsWith("//")
    || candidate.endsWith("/")
    || candidate.includes("?")
    || candidate.includes("#")
    || hasUnsafeCharacters(candidate)
  ) {
    throw new Error(
      "NEXT_PUBLIC_BASE_PATH must be empty or start with one slash and have no trailing slash."
    );
  }

  const segments = candidate.slice(1).split("/");
  if (segments.some((segment) => !segment || segment === "." || segment === "..")) {
    throw new Error("NEXT_PUBLIC_BASE_PATH contains an invalid path segment.");
  }
  return candidate;
}

/** Returns the canonical application URL without a trailing slash. */
export function getAppUrl(
  siteOrigin = getSiteOrigin(),
  basePath = getBasePath()
) {
  const origin = getSiteOrigin(siteOrigin, process.env.NODE_ENV);
  return `${origin}${getBasePath(basePath)}`;
}

/**
 * Builds an absolute URL inside this application. Server Actions use absolute
 * destinations so both native form redirects and the Next client router keep
 * exactly one configured base path.
 */
export function buildAppUrl(
  path: string,
  siteOrigin = getSiteOrigin(),
  basePath = getBasePath()
) {
  return new URL(
    withBasePath(path, basePath),
    getSiteOrigin(siteOrigin, process.env.NODE_ENV)
  ).toString();
}

/**
 * Prefixes an internal URL for native browser APIs and public assets. Already
 * prefixed paths are preserved, making the operation idempotent.
 */
export function withBasePath(path: string, basePath = getBasePath()) {
  const base = getBasePath(basePath);
  if (
    typeof path !== "string"
    || !path.startsWith("/")
    || path.startsWith("//")
    || hasUnsafeCharacters(path)
  ) {
    throw new Error("Application paths must be root-relative internal URLs.");
  }

  const parsed = new URL(path, INTERNAL_URL_ORIGIN);
  if (parsed.origin !== INTERNAL_URL_ORIGIN) {
    throw new Error("Application paths must remain on the application origin.");
  }
  const suffix = `${parsed.search}${parsed.hash}`;
  const pathname = parsed.pathname;
  if (!base) return `${pathname}${suffix}`;
  if (pathname === base || pathname.startsWith(`${base}/`)) {
    return `${pathname}${suffix}`;
  }
  if (pathname === "/") return `${base}${suffix}`;
  return `${base}${pathname}${suffix}`;
}

/** Removes the configured prefix and returns a logical Next.js route. */
export function stripBasePath(path: string, basePath = getBasePath()) {
  const base = getBasePath(basePath);
  if (!base || typeof path !== "string") return path;

  const match = path.match(/^([^?#]*)([\s\S]*)$/);
  const pathname = match?.[1] ?? path;
  const suffix = match?.[2] ?? "";
  if (pathname === base) return `/${suffix}`;
  if (pathname.startsWith(`${base}/`)) return `${pathname.slice(base.length)}${suffix}`;
  return path;
}

/**
 * Accepts only same-application paths and normalizes them to logical routes
 * suitable for Next.js Link/redirect. A base-prefixed input is stripped.
 */
export function sanitizeInternalRedirect(
  value: unknown,
  fallback = DEFAULT_REDIRECT_PATH,
  basePath = getBasePath()
) {
  const safeFallback = normalizeInternalPath(fallback, "/", basePath) ?? DEFAULT_REDIRECT_PATH;
  return normalizeInternalPath(value, safeFallback, basePath) ?? safeFallback;
}

export function buildAuthCallbackUrl(
  next: unknown = "/reset-password",
  siteOrigin = getSiteOrigin(),
  basePath = getBasePath()
) {
  const callback = new URL(withBasePath("/auth/callback", basePath), getSiteOrigin(siteOrigin));
  callback.searchParams.set(
    "next",
    sanitizeInternalRedirect(next, "/reset-password", basePath)
  );
  return callback.toString();
}

/** Cookies are scoped to this application when it is mounted below a host. */
export function getCookiePath(basePath = getBasePath()) {
  return getBasePath(basePath) || "/";
}

function normalizeInternalPath(value: unknown, fallback: string, basePath: string) {
  if (
    typeof value !== "string"
    || !value.startsWith("/")
    || value.startsWith("//")
    || hasUnsafeCharacters(value)
  ) {
    return fallback;
  }

  try {
    const parsed = new URL(value, INTERNAL_URL_ORIGIN);
    if (parsed.origin !== INTERNAL_URL_ORIGIN) return fallback;
    const normalized = `${parsed.pathname}${parsed.search}${parsed.hash}`;
    return stripBasePath(normalized, basePath);
  } catch {
    return fallback;
  }
}

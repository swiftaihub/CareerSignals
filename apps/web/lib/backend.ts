import "server-only";

export interface BackendErrorPayload {
  detail?: string;
  error_code?: string;
  resets_at?: string;
}

export function getBackendBaseUrl(
  configured: string | null | undefined = process.env.API_BASE_URL,
  nodeEnv = process.env.NODE_ENV
) {
  const candidate = configured?.trim()
    || (nodeEnv === "production" ? "" : "http://localhost:8000");
  if (!candidate || /[\\\u0000-\u001f\u007f]/.test(candidate)) {
    throw new Error("API_BASE_URL must be configured as an absolute HTTP(S) origin.");
  }

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw new Error("API_BASE_URL must be configured as an absolute HTTP(S) origin.");
  }
  if (
    (parsed.protocol !== "http:" && parsed.protocol !== "https:")
    || parsed.username
    || parsed.password
    || parsed.pathname !== "/"
    || parsed.search
    || parsed.hash
  ) {
    throw new Error("API_BASE_URL must be an HTTP(S) origin without credentials or a path.");
  }
  const isLoopback = parsed.hostname === "localhost"
    || parsed.hostname === "127.0.0.1"
    || parsed.hostname === "[::1]";
  if (nodeEnv === "production" && parsed.protocol !== "https:" && !isLoopback) {
    throw new Error("API_BASE_URL must use HTTPS in production.");
  }
  return parsed.origin;
}

export async function backendFetch(path: string, init: RequestInit = {}) {
  return fetch(`${getBackendBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.headers || {})
    }
  });
}

export async function readBackendError(response: Response): Promise<BackendErrorPayload> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") {
      return payload;
    }
    if (payload?.detail && typeof payload.detail === "object") {
      return payload.detail;
    }
  } catch {
    // Use a generic public message below.
  }
  return { detail: "The request could not be completed.", error_code: "REQUEST_FAILED" };
}

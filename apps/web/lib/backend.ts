import "server-only";

export interface BackendErrorPayload {
  detail?: string;
  error_code?: string;
  resets_at?: string;
}

export function getBackendBaseUrl() {
  return (process.env.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
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

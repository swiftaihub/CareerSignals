const CLOUDFLARE_ORIGIN_TIMEOUT = 522;
const DEFAULT_MAX_ATTEMPTS = 4;
const DEFAULT_RETRY_DELAY_MS = 5_000;

export function containsMixedContent(body) {
  const httpUrlAttribute = /\b(?:action|formaction|href|poster|src|srcset)\s*=\s*["'][^"']*\bhttp:\/\//i;
  const httpCssUrl = /\burl\(\s*["']?http:\/\//i;
  return httpUrlAttribute.test(body) || httpCssUrl.test(body);
}

export function containsDuplicateBasePath(body, basePath) {
  if (!basePath) return false;
  const escaped = basePath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`${escaped}${escaped}(?=[/?#"'])`).test(body);
}

export async function requestWithRetry(url, options = {}) {
  const {
    fetchImpl = fetch,
    maxAttempts = DEFAULT_MAX_ATTEMPTS,
    retryDelayMs = DEFAULT_RETRY_DELAY_MS,
    sleep = delay,
    onRetry = console.warn,
    requestInit = {}
  } = options;

  if (!Number.isInteger(maxAttempts) || maxAttempts < 1) {
    throw new Error("maxAttempts must be a positive integer");
  }
  if (!Number.isFinite(retryDelayMs) || retryDelayMs < 0) {
    throw new Error("retryDelayMs must be a non-negative number");
  }

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const response = await fetchImpl(url, {
      ...requestInit,
      redirect: requestInit.redirect || "manual",
      headers: {
        "user-agent": "CareerSignals deployment smoke test",
        ...requestInit.headers
      }
    });
    if (response.status !== CLOUDFLARE_ORIGIN_TIMEOUT || attempt === maxAttempts) {
      return response;
    }

    const waitMs = retryDelayMs * (2 ** (attempt - 1));
    onRetry(
      `Smoke request ${new URL(url).pathname} returned 522 `
      + `(attempt ${attempt}/${maxAttempts}); retrying in ${waitMs}ms.`
    );
    await sleep(waitMs);
  }

  throw new Error("Smoke request retry loop exited unexpectedly");
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

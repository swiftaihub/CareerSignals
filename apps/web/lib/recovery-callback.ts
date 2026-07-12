import { extractSessionId, type RecoveryIntentIdentity } from "./password-recovery";

interface ExchangeResult {
  data: unknown;
  error: unknown;
}

export interface RecoveryCodeExchange {
  identity: RecoveryIntentIdentity;
  session: {
    access_token: string;
  };
}

export type RecoveryCodeExchangeResult =
  | { ok: true; value: RecoveryCodeExchange }
  | { ok: false; reason: "missing" | "invalid" | "not-recovery" };

export async function exchangeRecoveryCode(
  code: unknown,
  exchange: (code: string) => Promise<ExchangeResult>
): Promise<RecoveryCodeExchangeResult> {
  if (typeof code !== "string" || !code.trim()) {
    return { ok: false, reason: "missing" };
  }

  let result: ExchangeResult;
  try {
    result = await exchange(code);
  } catch {
    return { ok: false, reason: "invalid" };
  }
  if (result.error || !isRecord(result.data)) {
    return { ok: false, reason: "invalid" };
  }

  // Auth JS returns this runtime field when its PKCE verifier was created by
  // resetPasswordForEmail, even though older exported response types omit it.
  if (result.data.redirectType !== "recovery") {
    return { ok: false, reason: "not-recovery" };
  }

  const session = result.data.session;
  const user = result.data.user;
  if (!isRecord(session) || !isRecord(user)) {
    return { ok: false, reason: "invalid" };
  }
  const accessToken = session.access_token;
  const userId = user.id;
  const sessionId = extractSessionId(accessToken);
  if (typeof accessToken !== "string" || typeof userId !== "string" || !sessionId) {
    return { ok: false, reason: "invalid" };
  }

  return {
    ok: true,
    value: {
      identity: { userId, sessionId },
      session: { access_token: accessToken }
    }
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

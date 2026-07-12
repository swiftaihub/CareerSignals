import {
  DEMO_PASSWORD_CHANGE_MESSAGE,
  PASSWORD_CHANGE_SUCCESS_MESSAGE,
  RESET_REQUEST_SUCCESS_MESSAGE
} from "./password-policy";

export interface PublicPasswordState {
  error?: string;
  success?: string;
}

export interface AuthOperationError {
  code?: unknown;
  message?: unknown;
  name?: unknown;
  status?: unknown;
}

interface ResetRequestDependencies {
  email: string;
  redirectTo: string;
  send: (
    email: string,
    options: { redirectTo: string }
  ) => Promise<{ error: AuthOperationError | null }>;
}

interface PasswordUpdateDependencies {
  update: (
    attributes: { password: string; current_password?: string }
  ) => Promise<{ error: AuthOperationError | null }>;
  signOutGlobally: () => Promise<unknown>;
  clearLocalState?: () => Promise<unknown>;
  isDemo?: boolean;
}

const RATE_LIMIT_CODES = new Set([
  "over_email_send_rate_limit",
  "over_request_rate_limit",
  "rate_limit_exceeded"
]);

const SESSION_ERROR_CODES = new Set([
  "session_not_found",
  "session_expired",
  "refresh_token_not_found",
  "refresh_token_already_used"
]);

export async function requestPasswordReset({
  email,
  redirectTo,
  send
}: ResetRequestDependencies): Promise<PublicPasswordState> {
  try {
    const { error } = await send(email, { redirectTo });
    if (isRateLimitError(error)) {
      // A distinct per-address rate-limit response can itself disclose account
      // existence. Keep the same public result and let the UI's uniform
      // cooldown prevent rapid duplicate submissions.
      return { success: RESET_REQUEST_SUCCESS_MESSAGE };
    }
    if (isTransientAuthError(error)) {
      return {
        error: "Password reset email is temporarily unavailable. Please try again."
      };
    }

    // Supabase can return different internal responses depending on account
    // existence and project configuration. All other Auth responses
    // intentionally collapse to the same public result.
    return { success: RESET_REQUEST_SUCCESS_MESSAGE };
  } catch {
    return {
      error: "Password reset email is temporarily unavailable. Please try again."
    };
  }
}

export async function updateRecoveryPassword(
  password: string,
  { update, signOutGlobally, clearLocalState }: PasswordUpdateDependencies
): Promise<PublicPasswordState> {
  let result: { error: AuthOperationError | null };
  try {
    result = await update({ password });
  } catch {
    return { error: "Your password could not be updated. Please request a new reset link." };
  }

  if (result.error) {
    return { error: recoveryUpdateErrorMessage(result.error) };
  }

  try {
    await signOutGlobally();
  } catch {
    // The password is already changed. Callers still clear all browser-side
    // recovery state before returning a successful result.
  }
  try {
    await clearLocalState?.();
  } catch {
    // Browser state cleanup is also repeated by the server action adapter.
  }
  return { success: "updated" };
}

export async function updateAuthenticatedPassword(
  currentPassword: string,
  newPassword: string,
  {
    update,
    signOutGlobally,
    clearLocalState,
    isDemo
  }: PasswordUpdateDependencies
): Promise<PublicPasswordState> {
  if (isDemo) {
    return { error: DEMO_PASSWORD_CHANGE_MESSAGE };
  }

  let result: { error: AuthOperationError | null };
  try {
    result = await update({
      password: newPassword,
      current_password: currentPassword
    });
  } catch {
    return { error: "Your password could not be changed. Please try again." };
  }

  if (result.error) {
    return { error: authenticatedUpdateErrorMessage(result.error) };
  }

  try {
    await signOutGlobally();
  } catch {
    // The password change has completed. Local cookie cleanup remains the
    // caller's responsibility even if remote session revocation fails.
  }
  try {
    await clearLocalState?.();
  } catch {
    // The action adapter repeats cookie cleanup before returning success.
  }
  return { success: PASSWORD_CHANGE_SUCCESS_MESSAGE };
}

export function isRateLimitError(error: AuthOperationError | null | undefined) {
  if (!error) return false;
  const code = normalizedCode(error);
  const message = normalizedMessage(error);
  return error.status === 429
    || RATE_LIMIT_CODES.has(code)
    || message.includes("rate limit")
    || message.includes("too many requests");
}

export function isTransientAuthError(error: AuthOperationError | null | undefined) {
  if (!error) return false;
  const name = typeof error.name === "string" ? error.name : "";
  const message = normalizedMessage(error);
  return name === "AuthRetryableFetchError"
    || message.includes("fetch failed")
    || message.includes("network request failed");
}

export function recoveryUpdateErrorMessage(error: AuthOperationError) {
  const code = normalizedCode(error);
  if (SESSION_ERROR_CODES.has(code) || code === "otp_expired" || code === "flow_state_expired") {
    return "This password reset link is invalid or has expired. Request a new reset email.";
  }
  if (code === "same_password") {
    return "Choose a password that is different from your current password.";
  }
  if (code === "weak_password") {
    return "Password must be at least 10 characters.";
  }
  return "Your password could not be updated. Please request a new reset link.";
}

export function authenticatedUpdateErrorMessage(error: AuthOperationError) {
  const code = normalizedCode(error);
  const message = normalizedMessage(error);
  if (code === "current_password_required") return "Enter your current password.";
  if (
    code === "current_password_invalid"
    || code === "current_password_mismatch"
    || code === "invalid_credentials"
    || message.includes("current password")
  ) {
    return "Current password is incorrect.";
  }
  if (code === "same_password") {
    return "Choose a new password that is different from your current password.";
  }
  if (code === "weak_password") {
    return "Password must be at least 10 characters.";
  }
  if (SESSION_ERROR_CODES.has(code)) {
    return "Your session has expired. Please sign in again.";
  }
  return "Your password could not be changed. Please try again.";
}

function normalizedCode(error: AuthOperationError) {
  return typeof error.code === "string" ? error.code.toLowerCase() : "";
}

function normalizedMessage(error: AuthOperationError) {
  return typeof error.message === "string" ? error.message.toLowerCase() : "";
}

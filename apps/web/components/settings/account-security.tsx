"use client";

import {
  useActionState,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState
} from "react";
import { KeyRound, Loader2 } from "lucide-react";

import {
  changePasswordAction,
  type AuthActionState
} from "@/app/(auth)/actions";
import { SectionCard } from "@/components/shared/section-card";
import {
  DEMO_PASSWORD_CHANGE_MESSAGE,
  PASSWORD_MIN_LENGTH
} from "@/lib/password-policy";

const INITIAL_STATE: AuthActionState = {};
const UNSAVED_PREFERENCES_MESSAGE =
  "Save or discard your unsaved preference changes before changing your password.";

function ChangePasswordForm({
  id,
  disabled,
  onClose,
  onLockedChange
}: {
  id: string;
  disabled: boolean;
  onClose: () => void;
  onLockedChange: (locked: boolean) => void;
}) {
  const currentPasswordRef = useRef<HTMLInputElement>(null);
  const passwordHelpId = useId();
  const [state, action, pending] = useActionState(
    changePasswordAction,
    INITIAL_STATE
  );
  const locked = pending;

  useEffect(() => {
    currentPasswordRef.current?.focus();
  }, []);

  useEffect(() => {
    onLockedChange(locked);
  }, [locked, onLockedChange]);

  useEffect(() => () => onLockedChange(false), [onLockedChange]);

  return (
    <div
      aria-label="Change password"
      className="border-t border-border pt-5"
      id={id}
      role="region"
    >
      <form action={action} aria-busy={pending}>
        <div className="grid gap-4 lg:max-w-xl">
          <label className="text-sm font-semibold" htmlFor={`${id}-current-password`}>
            Current password
            <input
              autoComplete="current-password"
              className="input mt-1"
              disabled={disabled || locked}
              id={`${id}-current-password`}
              name="currentPassword"
              ref={currentPasswordRef}
              required
              type="password"
            />
          </label>

          <label className="text-sm font-semibold" htmlFor={`${id}-new-password`}>
            New password
            <input
              aria-describedby={passwordHelpId}
              autoComplete="new-password"
              className="input mt-1"
              disabled={disabled || locked}
              id={`${id}-new-password`}
              minLength={PASSWORD_MIN_LENGTH}
              name="newPassword"
              required
              type="password"
            />
            <span
              className="mt-1 block text-xs font-normal text-muted-foreground"
              id={passwordHelpId}
            >
              Use at least {PASSWORD_MIN_LENGTH} characters.
            </span>
          </label>

          <label className="text-sm font-semibold" htmlFor={`${id}-confirm-password`}>
            Confirm new password
            <input
              autoComplete="new-password"
              className="input mt-1"
              disabled={disabled || locked}
              id={`${id}-confirm-password`}
              minLength={PASSWORD_MIN_LENGTH}
              name="confirmPassword"
              required
              type="password"
            />
          </label>
        </div>

        {state.error ? (
          <p
            className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-900"
            role="alert"
          >
            {state.error}
          </p>
        ) : null}

        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button
            className="btn"
            disabled={locked}
            type="button"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            disabled={disabled || locked}
            type="submit"
          >
            {pending ? (
              <>
                <Loader2
                  aria-hidden="true"
                  className="h-4 w-4 animate-spin motion-reduce:animate-none"
                />
                Updating…
              </>
            ) : (
              "Update password"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

export function AccountSecurity({
  readOnly,
  preferencesDirty,
  onBusyChange
}: {
  readOnly: boolean;
  preferencesDirty: boolean;
  onBusyChange?: (busy: boolean) => void;
}) {
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [formLocked, setFormLocked] = useState(false);
  const unavailable = readOnly || preferencesDirty;
  const closeForm = useCallback(() => {
    setOpen(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  }, []);
  const handleLockedChange = useCallback((locked: boolean) => {
    setFormLocked(locked);
  }, []);

  useEffect(() => {
    onBusyChange?.(formLocked);
    return () => onBusyChange?.(false);
  }, [formLocked, onBusyChange]);

  return (
    <SectionCard
      action={(
        <button
          aria-controls={panelId}
          aria-expanded={open}
          className="btn btn-primary"
          disabled={unavailable || formLocked}
          ref={triggerRef}
          type="button"
          onClick={() => setOpen((current) => !current)}
        >
          <KeyRound aria-hidden="true" className="h-4 w-4" />
          {open ? "Close" : "Change password"}
        </button>
      )}
      className="mt-6 scroll-mt-24"
      description="Manage your CareerSignals account password and sign-in security."
      title="Account Security"
    >
      {readOnly ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {DEMO_PASSWORD_CHANGE_MESSAGE}
        </p>
      ) : preferencesDirty ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {UNSAVED_PREFERENCES_MESSAGE}
        </p>
      ) : !open ? (
        <p className="text-sm text-muted-foreground">
          You will be signed out after your password is updated and must sign in again.
        </p>
      ) : null}

      {open ? (
        <ChangePasswordForm
          disabled={unavailable}
          id={panelId}
          onClose={closeForm}
          onLockedChange={handleLockedChange}
        />
      ) : null}
    </SectionCard>
  );
}

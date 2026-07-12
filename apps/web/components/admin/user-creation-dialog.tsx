"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { createAdminUser } from "@/lib/api-client";
import { PASSWORD_MIN_LENGTH, passwordSchema } from "@/lib/password-policy";
import type { AdminUser } from "@/lib/types";

const schema = z.object({
  username: z.string().min(3).max(32).regex(
    /^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$/,
    "Enter a valid username."
  ),
  email: z.email(),
  temporary_password: passwordSchema,
  require_password_change: z.boolean()
});
type Values = z.infer<typeof schema>;

export function UserCreationDialog({
  open,
  onClose,
  onCreated
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (user: AdminUser) => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    setError
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { require_password_change: true }
  });
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 p-4">
      <form
        className="w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-2xl"
        onSubmit={handleSubmit(async (values) => {
          try {
            const user = await createAdminUser(values);
            reset();
            onCreated(user);
            onClose();
          } catch (error) {
            setError("root", {
              message: error instanceof Error ? error.message : "User creation failed."
            });
          }
        })}
      >
        <h2 className="text-xl font-semibold">Create user</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The temporary password is submitted once and is never displayed afterward. New accounts begin in pending status.
        </p>
        <div className="mt-5 grid gap-4">
          <label className="text-sm font-semibold">
            Username
            <input className="input mt-1" autoComplete="off" {...register("username")} />
          </label>
          <label className="text-sm font-semibold">
            Email
            <input className="input mt-1" type="email" autoComplete="off" {...register("email")} />
          </label>
          <label className="text-sm font-semibold">
            Temporary password
            <input
              className="input mt-1"
              type="password"
              minLength={PASSWORD_MIN_LENGTH}
              autoComplete="new-password"
              {...register("temporary_password")}
            />
            <span className="mt-1 block text-xs font-normal text-muted-foreground">
              Use at least {PASSWORD_MIN_LENGTH} characters.
            </span>
          </label>
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" {...register("require_password_change")} />
            Require a password change
          </label>
        </div>
        {Object.values(errors)[0]?.message ? (
          <p className="mt-3 text-sm text-red-800">
            {String(Object.values(errors)[0]?.message)}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <button className="btn" type="button" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={isSubmitting} type="submit">
            {isSubmitting ? "Creating…" : "Create user"}
          </button>
        </div>
      </form>
    </div>
  );
}

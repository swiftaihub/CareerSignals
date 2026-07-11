"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";

import { EntitlementAdjustmentDialog } from "@/components/admin/entitlement-dialog";
import { UserCreationDialog } from "@/components/admin/user-creation-dialog";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { deleteAdminUser, getAdminUsers, mutateAdminUser } from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import type { AdminUser } from "@/lib/types";

type EntitlementMode = "grant-days" | "reduce-days";

export function UserManagementTable() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingUserUuid, setActingUserUuid] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [entitlement, setEntitlement] = useState<{
    user: AdminUser;
    mode: EntitlementMode;
  } | null>(null);
  const pageSize = 20;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getAdminUsers({
        page,
        page_size: pageSize,
        search: search || undefined,
        account_status: status || undefined,
        role: role || undefined
      });
      setUsers(result.items);
      setTotal(result.total);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("Users unavailable."));
    } finally {
      setLoading(false);
    }
  }, [page, role, search, status]);

  useEffect(() => {
    load();
  }, [load]);

  function replace(updated: AdminUser) {
    setUsers((current) => current.map((user) =>
      user.user_uuid === updated.user_uuid ? updated : user
    ));
  }

  async function runAction(user: AdminUser, name: string) {
    setMessage("");
    setError(null);
    if (name === "grant-days" || name === "reduce-days") {
      setEntitlement({ user, mode: name });
      return;
    }
    if (name === "delete") {
      if (!window.confirm(`Soft delete ${user.username}? Their sessions will be revoked.`)) return;
      setActingUserUuid(user.user_uuid);
      try {
        await deleteAdminUser(user.user_uuid);
        setMessage(`${user.username} was soft deleted.`);
        await load();
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError : new Error("Delete failed."));
      } finally {
        setActingUserUuid(null);
      }
      return;
    }

    setActingUserUuid(user.user_uuid);
    try {
      const result = await mutateAdminUser(user.user_uuid, name);
      if ("user_uuid" in result) {
        replace(result);
      } else {
        setMessage(result.detail);
        await load();
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError : new Error("User action failed."));
    } finally {
      setActingUserUuid(null);
    }
  }

  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap gap-3">
          <label className="text-xs font-semibold uppercase text-muted-foreground">
            Search
            <input
              className="input mt-1 normal-case"
              placeholder="UUID, username, or email"
              value={search}
              onChange={(event) => { setPage(1); setSearch(event.target.value); }}
            />
          </label>
          <label className="text-xs font-semibold uppercase text-muted-foreground">
            Status
            <select
              className="select mt-1 normal-case"
              value={status}
              onChange={(event) => { setPage(1); setStatus(event.target.value); }}
            >
              <option value="">All statuses</option>
              {["pending", "active", "expired", "suspended", "deleted"].map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="text-xs font-semibold uppercase text-muted-foreground">
            Role
            <select
              className="select mt-1 normal-case"
              value={role}
              onChange={(event) => { setPage(1); setRole(event.target.value); }}
            >
              <option value="">All roles</option>
              {["user", "admin", "demo"].map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
        </div>
        <button className="btn btn-primary" type="button" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" />Create user
        </button>
      </div>

      {message ? (
        <p className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status">
          {message}
        </p>
      ) : null}
      {error ? <ErrorState error={error} /> : null}
      {loading ? (
        <LoadingState label="Loading users…" />
      ) : (
        <div className="mt-5 table-shell overflow-x-auto">
          <table className="data-table min-w-[1300px]">
            <thead>
              <tr>
                <th>User UUID</th><th>Username</th><th>Email</th><th>Role</th><th>Status</th>
                <th>Created</th><th>Activated</th><th>Expiration</th><th>Days</th>
                <th>Last Login</th><th>Last Activity</th><th>Last Pipeline</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.user_uuid}>
                  <td className="font-mono text-xs">{user.user_uuid}</td>
                  <td className="font-semibold">{user.username}</td>
                  <td>{user.email || "—"}</td>
                  <td>{user.role}</td>
                  <td>{user.account_status}</td>
                  <td>{formatDateTime(user.created_at)}</td>
                  <td>{formatDateTime(user.activated_at)}</td>
                  <td>{user.expires_at ? formatDateTime(user.expires_at) : "Never"}</td>
                  <td>{user.remaining_days ?? "—"}</td>
                  <td>{formatDateTime(user.last_login_at)}</td>
                  <td>{formatDateTime(user.last_activity_at)}</td>
                  <td className="font-mono text-xs">{user.last_successful_pipeline_run_uuid || "—"}</td>
                  <td>
                    <select
                      aria-label={`Action for ${user.username}`}
                      className="select h-8 min-w-40 text-xs"
                      defaultValue=""
                      disabled={actingUserUuid === user.user_uuid}
                      onChange={(event) => {
                        const value = event.target.value;
                        event.target.value = "";
                        if (value) runAction(user, value);
                      }}
                    >
                      <option value="">{actingUserUuid === user.user_uuid ? "Working…" : "Choose action…"}</option>
                      <option value="activate">Activate</option>
                      <option value="expire">Expire now</option>
                      <option value="grant-days">Add days</option>
                      <option value="reduce-days">Reduce days</option>
                      <option value="suspend">Suspend</option>
                      <option value="restore">Restore</option>
                      <option value="reset-password">Reset password</option>
                      <option value="revoke-sessions">Revoke sessions</option>
                      <option value="delete">Soft delete</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
        <span>Page {page} of {pages} · {total} users</span>
        <div className="flex gap-2">
          <button className="btn" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
          <button className="btn" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</button>
        </div>
      </div>

      <UserCreationDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(user) => {
          setUsers((current) => [user, ...current]);
          setTotal((value) => value + 1);
          setMessage(`${user.username} was created in pending status.`);
        }}
      />
      <EntitlementAdjustmentDialog
        user={entitlement?.user || null}
        mode={entitlement?.mode || "grant-days"}
        onClose={() => setEntitlement(null)}
        onUpdated={(user) => {
          replace(user);
          setMessage(`Entitlement updated for ${user.username}.`);
        }}
      />
    </>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { getAdminAuditLogs } from "@/lib/api-client";
import { formatDateTime } from "@/lib/formatters";
import type { AdminAuditLog } from "@/lib/types";

export function AuditLogTable() {
  const [rows, setRows] = useState<AdminAuditLog[]>([]); const [total, setTotal] = useState(0); const [page, setPage] = useState(1); const [actionFilter, setActionFilter] = useState(""); const [loading, setLoading] = useState(true); const [error, setError] = useState<Error | null>(null); const pageSize = 25;
  const load = useCallback(async () => { setLoading(true); try { const result = await getAdminAuditLogs({ page, page_size: pageSize, action: actionFilter || undefined }); setRows(result.items); setTotal(result.total); } catch (requestError) { setError(requestError instanceof Error ? requestError : new Error("Audit logs unavailable.")); } finally { setLoading(false); } }, [actionFilter, page]);
  useEffect(() => { load(); }, [load]); const pages = Math.max(1, Math.ceil(total / pageSize));
  return <><label className="block max-w-sm text-xs font-semibold uppercase text-muted-foreground">Action filter<input className="input mt-1 normal-case" value={actionFilter} onChange={(event) => { setPage(1); setActionFilter(event.target.value); }} /></label>{error ? <ErrorState error={error} /> : null}{loading ? <LoadingState label="Loading audit logs…" /> : <div className="mt-5 table-shell overflow-x-auto"><table className="data-table min-w-[950px]"><thead><tr><th>Timestamp</th><th>Action</th><th>Admin</th><th>Target User</th><th>Request ID</th><th>Details</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.audit_uuid || `${row.created_at}-${index}`}><td>{formatDateTime(row.created_at)}</td><td className="font-semibold">{row.action}</td><td className="font-mono text-xs">{row.admin_user_uuid || "—"}</td><td className="font-mono text-xs">{row.target_user_uuid || "—"}</td><td className="font-mono text-xs">{row.request_id || "—"}</td><td><pre className="max-w-md overflow-x-auto whitespace-pre-wrap text-xs">{row.details ? JSON.stringify(row.details, null, 2) : "—"}</pre></td></tr>)}</tbody></table></div>}<div className="mt-4 flex items-center justify-between text-sm text-muted-foreground"><span>Page {page} of {pages} · {total} events</span><div className="flex gap-2"><button className="btn" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><button className="btn" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</button></div></div></>;
}

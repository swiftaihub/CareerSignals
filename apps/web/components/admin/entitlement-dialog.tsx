"use client";

import { useState } from "react";

import { mutateAdminUser } from "@/lib/api-client";
import type { AdminUser } from "@/lib/types";

export function EntitlementAdjustmentDialog({ user, mode, onClose, onUpdated }: { user: AdminUser | null; mode: "grant-days" | "reduce-days"; onClose: () => void; onUpdated: (user: AdminUser) => void }) {
  const [days, setDays] = useState(30); const [note, setNote] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  if (!user) return null;
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 p-4"><div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-2xl"><h2 className="text-xl font-semibold">{mode === "grant-days" ? "Add entitlement days" : "Reduce entitlement days"}</h2><p className="mt-1 text-sm text-muted-foreground">Adjusting {user.username}. Every change is audited.</p><label className="mt-5 block text-sm font-semibold">Days<input className="input mt-1" min={1} type="number" value={days} onChange={(event) => setDays(Number(event.target.value))} /></label><label className="mt-4 block text-sm font-semibold">Note<textarea className="textarea mt-1" value={note} onChange={(event) => setNote(event.target.value)} /></label>{error ? <p className="mt-3 text-sm text-red-800">{error}</p> : null}<div className="mt-6 flex justify-end gap-3"><button className="btn" type="button" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={busy || days < 1} type="button" onClick={async () => { setBusy(true); try { const updated = await mutateAdminUser(user.user_uuid, mode, { days, note }); onUpdated(updated); onClose(); } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Adjustment failed."); } finally { setBusy(false); } }}>{busy ? "Saving…" : "Confirm"}</button></div></div></div>;
}

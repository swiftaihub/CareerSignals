import { AuditLogTable } from "@/components/admin/audit-log-table";

export default function AdminAuditPage() { return <><div><div className="text-xs font-semibold uppercase text-primary">Administration</div><h1 className="mt-2 text-3xl font-bold">Audit logs</h1><p className="mt-2 text-sm text-muted-foreground">Evidence for every privileged account mutation.</p></div><div className="mt-6"><AuditLogTable /></div></>; }

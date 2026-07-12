import { UserManagementTable } from "@/components/admin/user-management-table";

export default function AdminUsersPage() { return <><div><div className="text-xs font-semibold uppercase text-primary">Administration</div><h1 className="mt-2 text-3xl font-bold">User management</h1><p className="mt-2 text-sm text-muted-foreground">Manage account lifecycle, entitlements, password-reset flows, and sessions. Existing passwords are never available.</p></div><div className="mt-6"><UserManagementTable /></div></>; }

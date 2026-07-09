import { Database, HardDrive } from "lucide-react";

import type { DataStatus } from "@/lib/types";

export function DataStatusBadge({ status }: { status?: DataStatus | null }) {
  const mode = status?.data_mode || "unknown";
  const isMotherDuck = mode === "motherduck";

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-sm">
      {isMotherDuck ? <Database className="h-3.5 w-3.5 text-primary" /> : <HardDrive className="h-3.5 w-3.5 text-primary" />}
      <span className="capitalize">{mode}</span>
      {status?.mart_tables_available ? (
        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-800">marts ready</span>
      ) : (
        <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-700">marts pending</span>
      )}
    </div>
  );
}

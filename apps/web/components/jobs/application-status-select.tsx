"use client";

import { APPLICATION_STATUSES } from "@/lib/constants";
import { cn } from "@/lib/utils";

export function ApplicationStatusSelect({
  value,
  disabled,
  className,
  onChange
}: {
  value?: string | null;
  disabled?: boolean;
  className?: string;
  onChange: (value: string) => void;
}) {
  return (
    <select
      className={cn("select h-8 min-w-32 text-xs", className)}
      disabled={disabled}
      value={value || "Not Applied"}
      onChange={(event) => onChange(event.target.value)}
    >
      {APPLICATION_STATUSES.map((status) => (
        <option key={status} value={status}>
          {status}
        </option>
      ))}
    </select>
  );
}

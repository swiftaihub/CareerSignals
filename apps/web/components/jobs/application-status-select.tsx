"use client";

import { APPLICATION_STATUSES } from "@/lib/constants";

export function ApplicationStatusSelect({
  value,
  disabled,
  onChange
}: {
  value?: string | null;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <select
      className="select h-8 min-w-32 text-xs"
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

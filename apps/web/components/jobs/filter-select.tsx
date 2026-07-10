"use client";

import type { ReactNode } from "react";

interface FilterSelectProps {
  label: string;
  value?: string;
  options: string[];
  placeholder?: string;
  children?: ReactNode;
  onChange: (value: string) => void;
}

export function FilterSelect({
  label,
  value,
  options,
  placeholder = "Any",
  children,
  onChange
}: FilterSelectProps) {
  return (
    <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
      {label}
      <select
        className="select normal-case"
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{placeholder}</option>
        {children}
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

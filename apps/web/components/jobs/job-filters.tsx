"use client";

import { APPLICATION_STATUSES, JOB_SORT_OPTIONS, VISA_SIGNALS, WORK_ARRANGEMENTS } from "@/lib/constants";
import type { JobFilters as JobFilterValues } from "@/lib/types";

interface JobFiltersProps {
  filters: JobFilterValues;
  onChange: (filters: JobFilterValues) => void;
  onReset: () => void;
}

function updateValue(
  filters: JobFilterValues,
  key: keyof JobFilterValues,
  value: string,
  onChange: (filters: JobFilterValues) => void
) {
  const parsedValue =
    key === "min_match_score" || key === "max_match_score"
      ? value
        ? Number(value)
        : undefined
      : value || undefined;
  onChange({ ...filters, page: 1, [key]: parsedValue });
}

export function JobFilters({ filters, onChange, onReset }: JobFiltersProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-soft">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Search
          <input
            className="input normal-case"
            placeholder="Role, company, skill, summary..."
            value={filters.search || ""}
            onChange={(event) => updateValue(filters, "search", event.target.value, onChange)}
          />
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Category
          <input
            className="input normal-case"
            placeholder="Analytics Engineer"
            value={filters.category_name || ""}
            onChange={(event) => updateValue(filters, "category_name", event.target.value, onChange)}
          />
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Company
          <input
            className="input normal-case"
            placeholder="Company name"
            value={filters.company || ""}
            onChange={(event) => updateValue(filters, "company", event.target.value, onChange)}
          />
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Industry
          <input
            className="input normal-case"
            placeholder="SaaS, banking..."
            value={filters.industry || ""}
            onChange={(event) => updateValue(filters, "industry", event.target.value, onChange)}
          />
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Location
          <input
            className="input normal-case"
            placeholder="Remote, New York..."
            value={filters.location || ""}
            onChange={(event) => updateValue(filters, "location", event.target.value, onChange)}
          />
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Work Arrangement
          <select
            className="select normal-case"
            value={filters.work_arrangement || ""}
            onChange={(event) => updateValue(filters, "work_arrangement", event.target.value, onChange)}
          >
            <option value="">Any</option>
            {WORK_ARRANGEMENTS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Visa Signal
          <select
            className="select normal-case"
            value={filters.visa_signal || ""}
            onChange={(event) => updateValue(filters, "visa_signal", event.target.value, onChange)}
          >
            <option value="">Any</option>
            {VISA_SIGNALS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Application Status
          <select
            className="select normal-case"
            value={filters.application_status || ""}
            onChange={(event) => updateValue(filters, "application_status", event.target.value, onChange)}
          >
            <option value="">Any</option>
            {APPLICATION_STATUSES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Min Score
          <input
            className="input normal-case"
            max={100}
            min={0}
            placeholder="80"
            type="number"
            value={filters.min_match_score ?? ""}
            onChange={(event) => updateValue(filters, "min_match_score", event.target.value, onChange)}
          />
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Max Score
          <input
            className="input normal-case"
            max={100}
            min={0}
            placeholder="100"
            type="number"
            value={filters.max_match_score ?? ""}
            onChange={(event) => updateValue(filters, "max_match_score", event.target.value, onChange)}
          />
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Sort By
          <select
            className="select normal-case"
            value={filters.sort_by || "match_score"}
            onChange={(event) => updateValue(filters, "sort_by", event.target.value, onChange)}
          >
            {JOB_SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
          Sort Order
          <select
            className="select normal-case"
            value={filters.sort_order || "desc"}
            onChange={(event) => updateValue(filters, "sort_order", event.target.value, onChange)}
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </label>
      </div>
      <div className="mt-3 flex justify-end">
        <button className="btn" type="button" onClick={onReset}>
          Reset Filters
        </button>
      </div>
    </div>
  );
}

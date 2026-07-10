"use client";

import { DateRangeFilter } from "@/components/jobs/date-range-filter";
import { FilterSelect } from "@/components/jobs/filter-select";
import { APPLICATION_STATUSES, JOB_SORT_OPTIONS, VISA_SIGNALS, WORK_ARRANGEMENTS } from "@/lib/constants";
import type { JobFilterOptions, JobFilters as JobFilterValues } from "@/lib/types";

interface JobFiltersProps {
  filters: JobFilterValues;
  options: JobFilterOptions;
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

export function JobFilters({ filters, options, onChange, onReset }: JobFiltersProps) {
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
        <FilterSelect
          label="Category"
          options={options.categories}
          placeholder="Any category"
          value={filters.category_name}
          onChange={(value) => updateValue(filters, "category_name", value, onChange)}
        />
        <FilterSelect
          label="Company"
          options={options.companies}
          placeholder="Any company"
          value={filters.company}
          onChange={(value) => updateValue(filters, "company", value, onChange)}
        />
        <FilterSelect
          label="Industry"
          options={options.industries}
          placeholder="Any industry"
          value={filters.industry}
          onChange={(value) => updateValue(filters, "industry", value, onChange)}
        />
        <FilterSelect
          label="Location"
          options={options.locations}
          placeholder="Any location"
          value={filters.location}
          onChange={(value) => updateValue(filters, "location", value, onChange)}
        />
        <FilterSelect
          label="Work"
          options={WORK_ARRANGEMENTS}
          value={filters.work_arrangement}
          onChange={(value) => updateValue(filters, "work_arrangement", value, onChange)}
        />
        <FilterSelect
          label="Visa"
          options={VISA_SIGNALS}
          value={filters.visa_signal}
          onChange={(value) => updateValue(filters, "visa_signal", value, onChange)}
        />
        <FilterSelect
          label="Status"
          options={APPLICATION_STATUSES}
          value={filters.application_status}
          onChange={(value) => updateValue(filters, "application_status", value, onChange)}
        />
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
      <div className="mt-4 border-t border-border pt-4">
        <DateRangeFilter
          endDate={filters.posted_end_date}
          startDate={filters.posted_start_date}
          onEndDateChange={(value) => updateValue(filters, "posted_end_date", value, onChange)}
          onReset={() => onChange({ ...filters, page: 1, posted_end_date: undefined, posted_start_date: undefined })}
          onStartDateChange={(value) => updateValue(filters, "posted_start_date", value, onChange)}
        />
      </div>
      <div className="mt-3 flex justify-end">
        <button className="btn" type="button" onClick={onReset}>
          Reset Filters
        </button>
      </div>
    </div>
  );
}

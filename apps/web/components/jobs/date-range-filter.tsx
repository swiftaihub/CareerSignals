"use client";

interface DateRangeFilterProps {
  startDate?: string;
  endDate?: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
  onReset: () => void;
}

export function DateRangeFilter({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onReset
}: DateRangeFilterProps) {
  const hasDateFilter = Boolean(startDate || endDate);

  return (
    <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
      <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
        Posted From
        <input
          className="input normal-case"
          type="date"
          value={startDate || ""}
          onChange={(event) => onStartDateChange(event.target.value)}
        />
      </label>
      <label className="space-y-1 text-xs font-semibold uppercase text-muted-foreground">
        Posted To
        <input
          className="input normal-case"
          type="date"
          value={endDate || ""}
          onChange={(event) => onEndDateChange(event.target.value)}
        />
      </label>
      <button
        className="btn h-10"
        disabled={!hasDateFilter}
        type="button"
        onClick={onReset}
      >
        Reset Dates
      </button>
    </div>
  );
}

"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, Plus, Search, X } from "lucide-react";

import {
  addTagValue,
  mergePreferenceOptions,
  normalizeTag,
  searchableOptions
} from "@/lib/preferences";
import type { PreferenceOption } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SearchableMultiSelectProps {
  id?: string;
  label: string;
  description?: string;
  placeholder?: string;
  values: string[];
  options: PreferenceOption[];
  onChange: (values: string[]) => void;
  allowCustom?: boolean;
  disabled?: boolean;
  maximum?: number;
  error?: string;
  className?: string;
  onSearch?: (query: string) => Promise<PreferenceOption[]>;
}

export function SearchableMultiSelect({
  id,
  label,
  description,
  placeholder = "Search or add a value",
  values,
  options,
  onChange,
  allowCustom = true,
  disabled = false,
  maximum = 50,
  error,
  className,
  onSearch
}: SearchableMultiSelectProps) {
  const generatedId = useId();
  const inputId = id || `multi-select-${generatedId}`;
  const listboxId = `${inputId}-listbox`;
  const helpId = `${inputId}-help`;
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [remoteOptions, setRemoteOptions] = useState<PreferenceOption[]>([]);
  const [searching, setSearching] = useState(false);
  const combinedOptions = useMemo(
    () => mergePreferenceOptions(options, remoteOptions),
    [options, remoteOptions]
  );
  const visibleOptions = useMemo(
    () => searchableOptions(combinedOptions, query, values).slice(0, 40),
    [combinedOptions, query, values]
  );
  const customValue = normalizeTag(query);
  const canCreate = allowCustom
    && Boolean(customValue)
    && customValue.length <= 120
    && !values.some((value) => value.toLocaleLowerCase() === customValue.toLocaleLowerCase())
    && !combinedOptions.some((option) =>
      option.value.toLocaleLowerCase() === customValue.toLocaleLowerCase()
      || option.label.toLocaleLowerCase() === customValue.toLocaleLowerCase()
    );
  const rowCount = visibleOptions.length + (canCreate ? 1 : 0);

  useEffect(() => {
    function closeOnOutsideClick(event: MouseEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  useEffect(() => {
    const normalizedQuery = normalizeTag(query);
    if (!onSearch || !open || normalizedQuery.length < 2) {
      setRemoteOptions([]);
      setSearching(false);
      return;
    }
    let active = true;
    setSearching(true);
    const timeout = window.setTimeout(() => {
      onSearch(normalizedQuery)
        .then((next) => {
          if (active) setRemoteOptions(next);
        })
        .catch(() => {
          if (active) setRemoteOptions([]);
        })
        .finally(() => {
          if (active) setSearching(false);
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [onSearch, open, query]);

  function choose(candidate: string) {
    const normalized = normalizeTag(candidate);
    if (!normalized) return;
    const next = maximum === 1 ? [normalized] : addTagValue(values, normalized, maximum);
    onChange(next);
    setQuery("");
    setHighlightedIndex(0);
    setOpen(false);
  }

  function remove(candidate: string) {
    onChange(values.filter((value) => value.toLocaleLowerCase() !== candidate.toLocaleLowerCase()));
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setHighlightedIndex((current) => Math.min(current + 1, Math.max(rowCount - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const option = visibleOptions[highlightedIndex];
      if (option) choose(option.value);
      else if (canCreate) choose(customValue);
    } else if (event.key === "Escape") {
      setOpen(false);
    } else if (event.key === "Backspace" && !query && values.length) {
      remove(values.at(-1) || "");
    }
  }

  return (
    <div className={cn("space-y-2", className)} ref={wrapperRef}>
      <div>
        <label className="text-sm font-semibold text-foreground" htmlFor={inputId}>{label}</label>
        {description ? <p className="mt-0.5 text-xs leading-5 text-muted-foreground" id={helpId}>{description}</p> : null}
      </div>
      <div className={cn(
        "relative rounded-lg border border-border bg-card transition focus-within:border-primary focus-within:ring-2 focus-within:ring-teal-600/15",
        error ? "border-red-400" : "",
        disabled ? "opacity-65" : ""
      )}>
        {values.length ? (
          <div className="flex flex-wrap gap-2 px-3 pt-3">
            {values.map((value) => {
              const display = options.find((option) => option.value === value)?.label || value;
              return (
                <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-sm font-medium text-teal-900" key={value}>
                  <span className="truncate">{display}</span>
                  <button
                    aria-label={`Remove ${display}`}
                    className="rounded-full p-0.5 hover:bg-teal-100 focus:outline-none focus:ring-2 focus:ring-primary"
                    disabled={disabled}
                    type="button"
                    onClick={() => remove(value)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </span>
              );
            })}
          </div>
        ) : null}
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            aria-autocomplete="list"
            aria-controls={listboxId}
            aria-describedby={description ? helpId : undefined}
            aria-expanded={open}
            aria-invalid={Boolean(error)}
            className="h-11 w-full rounded-lg bg-transparent pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground"
            disabled={disabled}
            id={inputId}
            placeholder={values.length >= maximum ? `Maximum of ${maximum} selected` : placeholder}
            role="combobox"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
              setHighlightedIndex(0);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={handleKeyDown}
          />
        </div>
        {open && !disabled ? (
          <div className="absolute z-40 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-border bg-card p-2 shadow-xl" id={listboxId} role="listbox">
            {visibleOptions.map((option, index) => (
              <button
                aria-selected={false}
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-muted",
                  highlightedIndex === index ? "bg-muted" : ""
                )}
                key={option.value}
                role="option"
                type="button"
                onClick={() => choose(option.value)}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setHighlightedIndex(index)}
              >
                <span>{option.label}</span>
                <Check className="h-4 w-4 text-primary" />
              </button>
            ))}
            {canCreate ? (
              <button
                aria-selected={false}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium text-primary hover:bg-teal-50",
                  highlightedIndex === visibleOptions.length ? "bg-teal-50" : ""
                )}
                role="option"
                type="button"
                onClick={() => choose(customValue)}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setHighlightedIndex(visibleOptions.length)}
              >
                <Plus className="h-4 w-4" />Add “{customValue}”
              </button>
            ) : null}
            {searching ? (
              <p className="px-3 py-2 text-xs text-muted-foreground" role="status">Searching shared job data…</p>
            ) : null}
            {!visibleOptions.length && !canCreate ? (
              <p className="px-3 py-4 text-sm text-muted-foreground">{searching ? "Looking for matches…" : "No matching options."}</p>
            ) : null}
          </div>
        ) : null}
      </div>
      {error ? <p className="text-xs font-medium text-red-700" role="alert">{error}</p> : null}
    </div>
  );
}

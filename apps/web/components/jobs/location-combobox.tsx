"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Search, X } from "lucide-react";

import type { JobFacets, LocationFacet, LocationGroupFacet } from "@/lib/types";
import { cn } from "@/lib/utils";

type LocationOption =
  | { kind: "group"; label: string; value: string; count: number }
  | { kind: "location"; label: string; group: string; value: string; count: number };

interface LocationComboboxProps {
  facets: JobFacets;
  location?: string;
  locationGroup?: string;
  loading?: boolean;
  onChange: (next: { location?: string; location_group?: string }) => void;
}

const DEFAULT_VISIBLE_PER_GROUP = 6;
const SEARCH_VISIBLE_PER_GROUP = 14;

function matchesQuery(value: string, query: string) {
  return value.toLowerCase().includes(query.toLowerCase());
}

function groupLocations(locations: LocationFacet[], query: string) {
  const byGroup = new Map<string, LocationFacet[]>();
  locations.forEach((location) => {
    const searchable = `${location.value} ${location.group}`;
    if (query && !matchesQuery(searchable, query)) {
      return;
    }
    const group = byGroup.get(location.group) || [];
    group.push(location);
    byGroup.set(location.group, group);
  });
  return byGroup;
}

function buildOptions(
  groups: LocationGroupFacet[],
  locations: LocationFacet[],
  query: string
): Array<{ heading: string; options: LocationOption[] }> {
  const sections: Array<{ heading: string; options: LocationOption[] }> = [];
  const normalizedQuery = query.trim();
  const locationGroups = groupLocations(locations, normalizedQuery);

  groups.forEach((group) => {
    const options: LocationOption[] = [];
    if (!normalizedQuery || matchesQuery(group.group, normalizedQuery)) {
      options.push({
        kind: "group",
        label: `All ${group.group}`,
        value: group.group,
        count: group.count
      });
    }

    const limit = normalizedQuery ? SEARCH_VISIBLE_PER_GROUP : DEFAULT_VISIBLE_PER_GROUP;
    const groupLocations = (locationGroups.get(group.group) || [])
      .sort((left, right) => right.count - left.count || left.value.localeCompare(right.value))
      .slice(0, limit);

    groupLocations.forEach((location) => {
      options.push({
        kind: "location",
        label: location.value,
        group: location.group,
        value: location.value,
        count: location.count
      });
    });

    if (options.length) {
      sections.push({ heading: group.group, options });
    }
  });

  return sections;
}

export function LocationCombobox({
  facets,
  location,
  locationGroup,
  loading,
  onChange
}: LocationComboboxProps) {
  const activeLabel = locationGroup || location || "";
  const [query, setQuery] = useState(activeLabel);
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [pendingFreeText, setPendingFreeText] = useState<string | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQuery(activeLabel);
  }, [activeLabel]);

  useEffect(() => {
    if (pendingFreeText === null) {
      return;
    }
    const handle = window.setTimeout(() => {
      onChange({
        location: pendingFreeText.trim() || undefined,
        location_group: undefined
      });
      setPendingFreeText(null);
    }, 350);
    return () => window.clearTimeout(handle);
  }, [onChange, pendingFreeText]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!wrapperRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const sections = useMemo(
    () => buildOptions(facets.location_groups, facets.locations, query),
    [facets.location_groups, facets.locations, query]
  );
  const flatOptions = sections.flatMap((section) => section.options);

  function selectOption(option: LocationOption) {
    setPendingFreeText(null);
    setQuery(option.kind === "group" ? option.value : option.label);
    setOpen(false);
    setHighlightedIndex(0);
    if (option.kind === "group") {
      onChange({ location_group: option.value, location: undefined });
      return;
    }
    onChange({ location: option.value, location_group: undefined });
  }

  function clearFilter() {
    setPendingFreeText(null);
    setQuery("");
    setOpen(false);
    setHighlightedIndex(0);
    onChange({ location: undefined, location_group: undefined });
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setHighlightedIndex((current) => Math.min(current + 1, Math.max(flatOptions.length - 1, 0)));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.max(current - 1, 0));
    }
    if (event.key === "Enter" && open && flatOptions[highlightedIndex]) {
      event.preventDefault();
      selectOption(flatOptions[highlightedIndex]);
    }
    if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const hasActiveFilter = Boolean(location || locationGroup);

  return (
    <div ref={wrapperRef} className="relative space-y-1 text-xs font-semibold uppercase text-muted-foreground">
      <label htmlFor="location-filter">Location</label>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          aria-autocomplete="list"
          aria-controls="location-filter-listbox"
          aria-expanded={open}
          aria-label="Search or select a location"
          className="input pl-9 pr-10 normal-case"
          id="location-filter"
          placeholder={loading ? "Loading locations..." : "Search city, state, region, remote..."}
          role="combobox"
          value={query}
          onChange={(event) => {
            const value = event.target.value;
            setQuery(value);
            setOpen(true);
            setHighlightedIndex(0);
            setPendingFreeText(value);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        {hasActiveFilter || query ? (
          <button
            aria-label="Clear location filter"
            className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
            type="button"
            onClick={clearFilter}
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      {hasActiveFilter ? (
        <div className="flex items-center gap-2 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-xs normal-case text-teal-900">
          <span className="font-semibold">{locationGroup ? "Region" : "Location"}:</span>
          <span className="truncate">{locationGroup || location}</span>
        </div>
      ) : null}

      {open ? (
        <div
          className="absolute z-30 mt-1 max-h-96 w-full overflow-y-auto rounded-lg border border-border bg-card p-2 text-sm normal-case text-foreground shadow-soft"
          id="location-filter-listbox"
          role="listbox"
        >
          {loading ? (
            <div className="px-3 py-4 text-sm text-muted-foreground">Loading locations...</div>
          ) : sections.length ? (
            sections.map((section) => (
              <div key={section.heading} className="py-1">
                <div className="px-2 py-1 text-xs font-semibold uppercase text-muted-foreground">
                  {section.heading}
                </div>
                {section.options.map((option) => {
                  const optionIndex = flatOptions.indexOf(option);
                  const isActive =
                    (option.kind === "group" && option.value === locationGroup) ||
                    (option.kind === "location" && option.value === location);
                  return (
                    <button
                      key={`${option.kind}-${option.value}`}
                      className={cn(
                        "flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left hover:bg-muted",
                        highlightedIndex === optionIndex ? "bg-muted" : ""
                      )}
                      role="option"
                      type="button"
                      aria-selected={isActive}
                      onMouseDown={(event) => event.preventDefault()}
                      onMouseEnter={() => setHighlightedIndex(optionIndex)}
                      onClick={() => selectOption(option)}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{option.label}</span>
                        {option.kind === "location" ? (
                          <span className="block text-xs text-muted-foreground">{option.group}</span>
                        ) : null}
                      </span>
                      <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                        {option.count}
                        {isActive ? <Check className="h-3.5 w-3.5 text-primary" /> : null}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))
          ) : (
            <div className="px-3 py-4 text-sm text-muted-foreground">No matching locations</div>
          )}
        </div>
      ) : null}
    </div>
  );
}

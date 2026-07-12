import { CircleDollarSign, MapPin, Search, ShieldCheck } from "lucide-react";

import { ChoiceChipGroup } from "@/components/settings/choice-chip-group";
import { SearchableMultiSelect } from "@/components/settings/searchable-multi-select";
import { SectionCard } from "@/components/shared/section-card";
import type {
  PreferenceDynamicOptionKind,
  PreferenceOption,
  PreferencesOptions,
  SearchPreferences
} from "@/lib/types";

const WORK_FALLBACK: PreferenceOption[] = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "on_site", label: "On-site" }
];

const EMPLOYMENT_FALLBACK: PreferenceOption[] = [
  { value: "full_time", label: "Full-time" },
  { value: "part_time", label: "Part-time" },
  { value: "contract", label: "Contract" },
  { value: "temporary", label: "Temporary" },
  { value: "internship", label: "Internship" },
  { value: "apprenticeship", label: "Apprenticeship" },
  { value: "freelance", label: "Freelance" },
  { value: "other", label: "Other" }
];

const VISA_FALLBACK: PreferenceOption[] = [
  { value: "sponsorship_required", label: "Sponsorship required" },
  { value: "h1b_transfer_required", label: "H-1B transfer required" },
  { value: "sponsorship_preferred", label: "Sponsorship preferred" },
  { value: "no_sponsorship_required", label: "No sponsorship required" },
  { value: "regardless", label: "Open regardless of sponsorship signal" }
];

function available(options: PreferenceOption[], fallback: PreferenceOption[]) {
  return options.length ? options : fallback;
}

function salaryValue(value: string) {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function SearchPreferencesForm({
  value,
  options,
  disabled,
  errors,
  loadOptions,
  onChange
}: {
  value: SearchPreferences;
  options: PreferencesOptions;
  disabled: boolean;
  errors: string[];
  loadOptions?: (kind: PreferenceDynamicOptionKind, query: string) => Promise<PreferenceOption[]>;
  onChange: (value: SearchPreferences) => void;
}) {
  function update<Key extends keyof SearchPreferences>(key: Key, next: SearchPreferences[Key]) {
    onChange({ ...value, [key]: next });
  }
  const titleError = errors.find((error) => error.toLocaleLowerCase().includes("job title"));
  const salaryError = errors.find((error) => error.toLocaleLowerCase().includes("salary") || error.toLocaleLowerCase().includes("currency"));

  return (
    <SectionCard
      className="mt-6 scroll-mt-24"
      title="Search Preferences"
      description="Tell CareerSignals what a worthwhile opportunity looks like. Search expansions and system keywords are generated for you."
    >
      <div className="space-y-7" id="search-preferences">
        <div className="grid gap-5 lg:grid-cols-2">
          <SearchableMultiSelect
            allowCustom
            disabled={disabled}
            error={titleError}
            id="preferred-job-titles"
            label="Job titles"
            description="Add only the roles you want. We generate useful title variations behind the scenes."
            options={options.job_titles}
            placeholder="Search or add a role, such as Product Manager"
            values={value.job_titles}
            onChange={(next) => update("job_titles", next)}
            onSearch={loadOptions ? (query) => loadOptions("job_titles", query) : undefined}
          />
          <SearchableMultiSelect
            allowCustom
            disabled={disabled}
            id="preferred-industries"
            label="Industries"
            description="Choose suggested industries or add your own."
            options={options.industries}
            placeholder="Search or add an industry"
            values={value.industries}
            onChange={(next) => update("industries", next)}
            onSearch={loadOptions ? (query) => loadOptions("industries", query) : undefined}
          />
          <SearchableMultiSelect
            allowCustom
            disabled={disabled}
            id="preferred-seniority"
            label="Seniority"
            options={options.seniority_levels}
            placeholder="Search seniority levels"
            values={value.seniority}
            onChange={(next) => update("seniority", next)}
          />
          <SearchableMultiSelect
            allowCustom={false}
            disabled={disabled}
            id="preferred-country"
            label="Country"
            description="Search the full country catalog."
            maximum={1}
            options={options.countries}
            placeholder="Search countries"
            values={value.country ? [value.country] : []}
            onChange={(next) => update("country", next[0] || "")}
          />
          <SearchableMultiSelect
            allowCustom
            className="lg:col-span-2"
            disabled={disabled}
            id="preferred-locations"
            label="Locations"
            description="Add cities, states or regions, metro areas, or country-level locations."
            options={options.locations}
            placeholder="Search or add locations"
            values={value.locations}
            onChange={(next) => update("locations", next)}
            onSearch={loadOptions ? (query) => loadOptions("locations", query) : undefined}
          />
        </div>

        <div className="grid gap-6 rounded-xl border border-border bg-background/70 p-4 lg:grid-cols-2">
          <ChoiceChipGroup
            disabled={disabled}
            label="Work arrangement"
            description="Select every arrangement you would consider."
            options={available(options.work_arrangements, WORK_FALLBACK)}
            selected={value.work_arrangements}
            onChange={(next) => update("work_arrangements", next)}
          />
          <ChoiceChipGroup
            disabled={disabled}
            label="Employment type"
            description="Choose one or more employment relationships."
            options={available(options.employment_types, EMPLOYMENT_FALLBACK)}
            selected={value.employment_types}
            onChange={(next) => update("employment_types", next)}
          />
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <SearchableMultiSelect
            allowCustom={false}
            disabled={disabled}
            id="visa-preferences"
            label="Visa preferences"
            description="Choose the statements that apply. CareerSignals manages the underlying keyword logic."
            options={available(options.visa_options, VISA_FALLBACK)}
            placeholder="Select visa preferences"
            values={value.visa_preferences}
            onChange={(next) => update("visa_preferences", next)}
          />
          <div className="rounded-xl border border-teal-100 bg-teal-50/70 p-4 text-sm text-teal-950">
            <div className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4" />System-managed signals</div>
            <p className="mt-2 leading-6 text-teal-900">Positive and negative sponsorship phrases stay managed by CareerSignals, so you never need to maintain keyword lists.</p>
          </div>
          <SearchableMultiSelect
            allowCustom
            disabled={disabled}
            id="excluded-companies"
            label="Excluded companies"
            description="Suggestions come from shared job data; custom company names are welcome."
            options={options.companies}
            placeholder="Search or add companies"
            values={value.excluded_companies}
            onChange={(next) => update("excluded_companies", next)}
            onSearch={loadOptions ? (query) => loadOptions("companies", query) : undefined}
          />
          <SearchableMultiSelect
            allowCustom
            disabled={disabled}
            id="excluded-titles"
            label="Excluded titles"
            description="Roles containing these titles will be deprioritized or excluded."
            options={options.job_titles}
            placeholder="Search or add excluded titles"
            values={value.excluded_titles}
            onChange={(next) => update("excluded_titles", next)}
            onSearch={loadOptions ? (query) => loadOptions("job_titles", query) : undefined}
          />
        </div>

        <div className="rounded-xl border border-border bg-background/70 p-4">
          <div className="flex items-start gap-3">
            <span className="rounded-lg bg-teal-50 p-2 text-primary"><CircleDollarSign className="h-5 w-5" /></span>
            <div><h3 className="font-semibold">Compensation</h3><p className="mt-1 text-sm text-muted-foreground">Optional values help salary matching without excluding jobs that omit compensation.</p></div>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <label className="text-sm font-semibold">Minimum acceptable salary
              <input className="input mt-1" disabled={disabled} min={0} inputMode="numeric" type="number" value={value.compensation.minimum_salary ?? ""} onChange={(event) => update("compensation", { ...value.compensation, minimum_salary: salaryValue(event.target.value) })} />
            </label>
            <label className="text-sm font-semibold">Preferred salary
              <input className="input mt-1" disabled={disabled} min={0} inputMode="numeric" type="number" value={value.compensation.preferred_salary ?? ""} onChange={(event) => update("compensation", { ...value.compensation, preferred_salary: salaryValue(event.target.value) })} />
            </label>
            <label className="text-sm font-semibold">Currency
              <input className="input mt-1 uppercase" disabled={disabled} list="currency-options" maxLength={3} placeholder="USD" value={value.compensation.currency} onChange={(event) => update("compensation", { ...value.compensation, currency: event.target.value.toUpperCase() })} />
              <datalist id="currency-options"><option value="USD" /><option value="CAD" /><option value="EUR" /><option value="GBP" /><option value="AUD" /><option value="INR" /><option value="JPY" /></datalist>
            </label>
            <label className="text-sm font-semibold">Salary period
              <select className="select mt-1" disabled={disabled} value={value.compensation.period} onChange={(event) => update("compensation", { ...value.compensation, period: event.target.value })}>
                <option value="annual">Annual</option><option value="monthly">Monthly</option><option value="hourly">Hourly</option>
              </select>
            </label>
          </div>
          {salaryError ? <p className="mt-3 text-sm font-medium text-red-700" role="alert">{salaryError}</p> : null}
        </div>

        <div className="flex flex-wrap gap-3 rounded-xl border border-cyan-100 bg-cyan-50/60 p-4 text-sm text-cyan-950">
          <Search className="h-5 w-5 shrink-0" />
          <p className="flex-1">Your titles, industries, work arrangement, and salary expectations automatically populate the system candidate profile. No duplicate entry is needed.</p>
          <MapPin className="h-5 w-5 shrink-0" />
        </div>
      </div>
    </SectionCard>
  );
}

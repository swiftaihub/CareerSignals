import { Check } from "lucide-react";

import type { PreferenceOption } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ChoiceChipGroup({
  label,
  description,
  options,
  selected,
  disabled,
  onChange
}: {
  label: string;
  description?: string;
  options: PreferenceOption[];
  selected: string[];
  disabled?: boolean;
  onChange: (values: string[]) => void;
}) {
  function toggle(value: string) {
    onChange(selected.includes(value)
      ? selected.filter((item) => item !== value)
      : [...selected, value]);
  }

  return (
    <fieldset>
      <legend className="text-sm font-semibold text-foreground">{label}</legend>
      {description ? <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{description}</p> : null}
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => {
          const active = selected.includes(option.value);
          return (
            <button
              aria-pressed={active}
              className={cn(
                "inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                active
                  ? "border-primary bg-teal-50 text-teal-900"
                  : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
              disabled={disabled}
              key={option.value}
              type="button"
              onClick={() => toggle(option.value)}
            >
              {active ? <Check className="h-4 w-4" /> : null}
              {option.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

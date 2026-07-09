import { cn } from "@/lib/utils";

const visaStyles: Record<string, string> = {
  Positive: "border-emerald-200 bg-emerald-50 text-emerald-800",
  Unknown: "border-neutral-200 bg-neutral-100 text-neutral-700",
  Negative: "border-amber-200 bg-amber-50 text-amber-800"
};

export function VisaSignalBadge({ signal }: { signal?: string | null }) {
  const label = signal || "Unknown";
  return <span className={cn("badge", visaStyles[label] || visaStyles.Unknown)}>{label}</span>;
}

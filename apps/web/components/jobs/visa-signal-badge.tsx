import { cn } from "@/lib/utils";

const visaStyles: Record<string, string> = {
  "Sponsorship Available": "border-emerald-200 bg-emerald-50 text-emerald-800",
  "No Sponsorship": "border-red-200 bg-red-50 text-red-800",
  "U.S. Citizenship Required": "border-red-200 bg-red-50 text-red-800",
  "Permanent Work Authorization Required": "border-amber-200 bg-amber-50 text-amber-900",
  Positive: "border-emerald-200 bg-emerald-50 text-emerald-800",
  Unknown: "border-neutral-200 bg-neutral-100 text-neutral-700",
  Negative: "border-red-200 bg-red-50 text-red-800"
};

function statusFromSignal(signal?: string | null) {
  if (signal === "Positive") {
    return "Sponsorship Available";
  }
  if (signal === "Negative") {
    return "No Sponsorship";
  }
  return "Unknown";
}

export function VisaSignalBadge({
  signal,
  status,
  evidence,
  confidence
}: {
  signal?: string | null;
  status?: string | null;
  evidence?: string | null;
  confidence?: string | null;
}) {
  const label = status || statusFromSignal(signal);
  const title = [confidence ? `Confidence: ${confidence}` : null, evidence ? `Evidence: ${evidence}` : null]
    .filter(Boolean)
    .join("\n");

  return (
    <span className={cn("badge max-w-full truncate", visaStyles[label] || visaStyles.Unknown)} title={title || label}>
      {label}
    </span>
  );
}

import { cn } from "@/lib/utils";

const statusStyles: Record<string, string> = {
  "Not Applied": "border-neutral-200 bg-neutral-100 text-neutral-700",
  Saved: "border-cyan-200 bg-cyan-50 text-cyan-800",
  Applied: "border-emerald-200 bg-emerald-50 text-emerald-800",
  Interview: "border-teal-200 bg-teal-50 text-teal-800",
  Rejected: "border-red-200 bg-red-50 text-red-800",
  Offer: "border-amber-200 bg-amber-50 text-amber-800",
  Archived: "border-neutral-200 bg-neutral-50 text-neutral-500"
};

export function StatusBadge({ status }: { status?: string | null }) {
  const label = status || "Not Applied";
  return <span className={cn("badge", statusStyles[label] || statusStyles["Not Applied"])}>{label}</span>;
}

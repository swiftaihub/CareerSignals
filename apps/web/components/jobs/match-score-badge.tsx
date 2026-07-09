import { formatScore } from "@/lib/formatters";
import { cn } from "@/lib/utils";

function scoreClass(score?: number | null) {
  if ((score || 0) >= 90) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if ((score || 0) >= 80) {
    return "border-teal-200 bg-teal-50 text-teal-800";
  }
  if ((score || 0) >= 70) {
    return "border-cyan-200 bg-cyan-50 text-cyan-800";
  }
  return "border-neutral-200 bg-neutral-100 text-neutral-700";
}

export function MatchScoreBadge({ score, tier }: { score?: number | null; tier?: string | null }) {
  return (
    <span className={cn("badge", scoreClass(score))}>
      {formatScore(score)}
      {tier ? <span className="ml-1 hidden md:inline">/ {tier}</span> : null}
    </span>
  );
}

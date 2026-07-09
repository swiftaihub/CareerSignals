import { DistributionChart } from "@/components/dashboard/distribution-chart";
import type { DistributionRow } from "@/lib/types";

export function WorkArrangementChart({ data }: { data: DistributionRow[] }) {
  return <DistributionChart data={data} />;
}

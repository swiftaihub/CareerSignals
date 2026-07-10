import { ExternalLink } from "lucide-react";

import type { Job } from "@/lib/types";

export function JobLinkButtons({ job }: { job: Job }) {
  return (
    <div className="flex flex-wrap gap-2">
      {job.jd_post_link ? (
        <a className="btn h-8 px-3 text-xs" href={job.jd_post_link} rel="noreferrer" target="_blank">
          JD
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : null}
      {job.apply_link ? (
        <a className="btn btn-primary h-8 px-3 text-xs" href={job.apply_link} rel="noreferrer" target="_blank">
          Apply
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : null}
    </div>
  );
}

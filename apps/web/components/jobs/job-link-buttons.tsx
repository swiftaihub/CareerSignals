import { ExternalLink } from "lucide-react";

import type { Job } from "@/lib/types";
import { safeExternalHttpUrl } from "@/lib/external-url";

export function JobLinkButtons({ job }: { job: Job }) {
  const jobDescriptionUrl = safeExternalHttpUrl(job.jd_post_link);
  const applicationUrl = safeExternalHttpUrl(job.apply_link);
  return (
    <div className="flex flex-wrap gap-2">
      {jobDescriptionUrl ? (
        <a className="btn h-8 px-3 text-xs" href={jobDescriptionUrl} rel="noopener noreferrer" target="_blank">
          JD
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : null}
      {applicationUrl ? (
        <a className="btn btn-primary h-8 px-3 text-xs" href={applicationUrl} rel="noopener noreferrer" target="_blank">
          Apply
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      ) : null}
    </div>
  );
}

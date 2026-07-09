"use client";

import { X } from "lucide-react";

import { ApplicationStatusSelect } from "@/components/jobs/application-status-select";
import { JobLinkButtons } from "@/components/jobs/job-link-buttons";
import { MatchScoreBadge } from "@/components/jobs/match-score-badge";
import { VisaSignalBadge } from "@/components/jobs/visa-signal-badge";
import { formatCurrency, formatDate, formatList, formatNullable } from "@/lib/formatters";
import type { Job } from "@/lib/types";

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm text-foreground">{value}</div>
    </div>
  );
}

export function JobDetailDrawer({
  job,
  open,
  updating,
  notes,
  onNotesChange,
  onClose,
  onStatusChange
}: {
  job: Job | null;
  open: boolean;
  updating?: boolean;
  notes: string;
  onNotesChange: (notes: string) => void;
  onClose: () => void;
  onStatusChange: (job: Job, status: string, notes?: string) => Promise<void>;
}) {
  if (!open || !job) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50">
      <button
        aria-label="Close job details"
        className="absolute inset-0 bg-neutral-950/35"
        type="button"
        onClick={onClose}
      />
      <aside className="absolute right-0 top-0 h-full w-full max-w-2xl overflow-y-auto border-l border-border bg-card p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <MatchScoreBadge score={job.match_score} tier={job.match_tier} />
              <VisaSignalBadge signal={job.visa_signal} />
            </div>
            <h2 className="mt-4 text-2xl font-bold text-foreground">
              {formatNullable(job.job_title)}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {formatNullable(job.company)} - {formatNullable(job.location)}
            </p>
          </div>
          <button className="btn h-9 w-9 p-0" type="button" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-6 grid gap-4 rounded-lg border border-border bg-muted/40 p-4 md:grid-cols-2">
          <DetailItem label="Category" value={formatNullable(job.category_name)} />
          <DetailItem label="Industry" value={formatNullable(job.industry)} />
          <DetailItem label="Work Arrangement" value={formatNullable(job.work_arrangement)} />
          <DetailItem label="Employment Type" value={formatNullable(job.employment_type)} />
          <DetailItem label="Seniority" value={formatNullable(job.seniority)} />
          <DetailItem label="Salary Midpoint" value={formatCurrency(job.salary_midpoint)} />
          <DetailItem label="Salary Range" value={formatNullable(job.salary_range_text)} />
          <DetailItem label="Date Posted" value={formatDate(job.date_posted)} />
        </div>

        <div className="mt-6 space-y-5">
          <section>
            <h3 className="text-sm font-semibold text-foreground">Reasoning Summary</h3>
            <p className="mt-2 rounded-lg border border-border bg-background p-4 text-sm leading-6 text-muted-foreground">
              {formatNullable(job.reasoning_summary)}
            </p>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <DetailItem label="Required Skills" value={formatList(job.required_skills)} />
            <DetailItem label="Preferred Skills" value={formatList(job.preferred_skills)} />
            <DetailItem label="All Extracted Skills" value={formatList(job.all_extracted_skills)} />
          </section>

          <section className="rounded-lg border border-border bg-background p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Application Workflow</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Status is stored for the personal user profile.
                </p>
              </div>
              <ApplicationStatusSelect
                disabled={updating}
                value={job.application_status}
                onChange={(value) => onStatusChange(job, value, notes)}
              />
            </div>
            <label className="mt-4 block text-xs font-semibold uppercase text-muted-foreground">
              Notes
              <textarea
                className="textarea mt-1 normal-case"
                placeholder="Add application notes, recruiter context, or next steps."
                value={notes}
                onChange={(event) => onNotesChange(event.target.value)}
              />
            </label>
            <div className="mt-4">
              <JobLinkButtons job={job} />
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

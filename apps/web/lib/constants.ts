import type { ApplicationStatus } from "@/lib/types";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "Not Applied",
  "Saved",
  "Applied",
  "Interview",
  "Rejected",
  "Offer",
  "Archived"
];

export const MATCH_TIERS = [
  "Excellent Match",
  "Strong Match",
  "Good Match",
  "Possible Match",
  "Low Priority"
];

export const WORK_ARRANGEMENTS = ["Remote", "Hybrid", "On-site", "Unknown"];

export const VISA_SIGNALS = ["Positive", "Unknown", "Negative"];

export const VISA_STATUSES = [
  "Sponsorship Available",
  "No Sponsorship",
  "U.S. Citizenship Required",
  "Permanent Work Authorization Required",
  "Unknown"
];

export const JOB_SORT_OPTIONS = [
  { value: "match_score", label: "Match score" },
  { value: "salary_midpoint", label: "Salary midpoint" },
  { value: "date_posted", label: "Date posted" },
  { value: "date_collected", label: "Date collected" },
  { value: "company", label: "Company" },
  { value: "job_title", label: "Job title" },
  { value: "category_name", label: "Category" }
];

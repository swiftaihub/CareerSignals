import { sanitizeInternalRedirect } from "./app-path";

export const AUTHENTICATED_NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/top-matches", label: "Top Matches" },
  { href: "/skill-gap", label: "Skill Gap" },
  { href: "/companies", label: "Companies" },
  { href: "/settings", label: "Settings" }
] as const;

export function safeRedirectPath(value: unknown, fallback = "/dashboard") {
  return sanitizeInternalRedirect(value, fallback);
}

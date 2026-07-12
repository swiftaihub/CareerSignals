export const AUTHENTICATED_NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/top-matches", label: "Top Matches" },
  { href: "/skill-gap", label: "Skill Gap" },
  { href: "/companies", label: "Companies" },
  { href: "/settings", label: "Settings" }
] as const;

export function safeRedirectPath(value: unknown, fallback = "/dashboard") {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }

  try {
    const parsed = new URL(value, "https://careersignals.invalid");
    return parsed.origin === "https://careersignals.invalid"
      ? `${parsed.pathname}${parsed.search}${parsed.hash}`
      : fallback;
  } catch {
    return fallback;
  }
}

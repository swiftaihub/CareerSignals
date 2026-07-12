export function formatCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not listed";
  }
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(value);
}

export function formatPercent(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "0%";
  }
  const normalized = value > 1 ? value / 100 : value;
  return new Intl.NumberFormat(undefined, {
    style: "percent",
    maximumFractionDigits: 1
  }).format(normalized);
}

export function formatScore(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return `${Math.round(value)}`;
}

export function formatDate(value?: string | null) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

export function formatDateTime(value?: string | null) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(date);
}

export function formatEasternDateTime(value?: string | null) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short"
  }).format(date);
}

export function formatNullable(value?: string | number | boolean | null) {
  if (value === null || value === undefined || value === "") {
    return "Unknown";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

export function formatList(values?: string[] | null, fallback = "None detected") {
  if (!values?.length) {
    return fallback;
  }
  return values.join(", ");
}

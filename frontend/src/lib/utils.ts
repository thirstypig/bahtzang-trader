export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

const TZ_KEY = "bahtzang_timezone";

export function getTimezone(): string {
  if (typeof window === "undefined") return "America/New_York";
  return localStorage.getItem(TZ_KEY) || Intl.DateTimeFormat().resolvedOptions().timeZone;
}

export function setTimezone(tz: string): void {
  localStorage.setItem(TZ_KEY, tz);
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    timeZone: getTimezone(),
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    timeZone: getTimezone(),
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

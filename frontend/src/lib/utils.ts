import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtPrice(v: number | null | undefined, precision = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: precision, maximumFractionDigits: precision });
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtDate(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const date = d.toISOString().slice(0, 10);
  return withTime ? `${date} ${d.toISOString().slice(11, 16)}Z` : date;
}

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "never";
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export const TIMEFRAME_CODES = ["1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M", "3M", "6M", "12M"];

export function signClass(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) return "text-muted-foreground";
  return v > 0 ? "text-bull" : "text-bear";
}

/** The oldest of several ISO times (e.g. the analysis time of each instrument): everything shown is at least this fresh. */
export function oldestTime(times: (string | null | undefined)[]): string | null {
  return times.filter((x): x is string => !!x).sort()[0] ?? null;
}

/** "+2.6R", "-0.5R", and "0.0R" for anything that rounds to zero (never "-0.0R"). */
export function fmtSignedR(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const r = Number(v.toFixed(digits));
  if (r === 0) return `${(0).toFixed(digits)}R`;
  return `${r > 0 ? "+" : ""}${r.toFixed(digits)}R`;
}

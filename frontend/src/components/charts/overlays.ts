import type { OverlayEvent, SwingPoint, TradePlan } from "@/lib/types";
import type { OverlayToggles } from "@/lib/store";

export interface ChartMarker {
  time: number;
  position: "aboveBar" | "belowBar" | "inBar";
  shape: "circle" | "square" | "arrowUp" | "arrowDown";
  color: string;
  text: string;
}

export interface ChartZone {
  from: number; // epoch seconds (origin bar)
  low: number;
  high: number;
  color: string;
  label: string;
}

export interface ChartLine {
  price: number;
  color: string;
  title: string;
  dashed?: boolean;
}

export const COLORS = {
  bull: "#4caf50",
  bear: "#ef5350",
  neutral: "#8a94a6",
  warn: "#f59e0b",
  primary: "#3b5bdb",
};

const ABBR: Record<string, string> = {
  bullish_engulfing: "Eng", bearish_engulfing: "Eng", hammer: "Ham", shooting_star: "SS", pin_bar: "Pin",
  morning_star: "MS", evening_star: "ES", doji: "Doji",
};
const ZONE_KINDS = new Set(["fvg", "order_block", "breaker_block", "demand_zone", "supply_zone"]);
const DEAD = new Set(["filled", "invalidated", "broken"]);

const dirColor = (d: string) => (d === "bullish" ? COLORS.bull : d === "bearish" ? COLORS.bear : COLORS.neutral);
const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

const MAX_STRUCTURE = 6;
const MAX_SWEEPS = 4;
const MAX_SWINGS = 10;
const MAX_PATTERNS = 6;
export const MAX_ZONES = 5;

const recent = <T extends { ts: number }>(xs: T[], visibleFrom: number, n: number) => xs.filter((x) => x.ts >= visibleFrom).slice(-n);

/** A readable chart shows a handful of the MOST RECENT items per layer (shapes, and text only where it carries meaning). */
export function buildMarkers(events: OverlayEvent[], swings: SwingPoint[], t: OverlayToggles, visibleFrom = 0): ChartMarker[] {
  const out: ChartMarker[] = [];
  if (t.swings) {
    for (const s of recent(swings, visibleFrom, MAX_SWINGS)) {
      out.push({
        time: s.ts, position: s.kind === "high" ? "aboveBar" : "belowBar", shape: "circle",
        color: s.label === "HH" || s.label === "HL" ? COLORS.bull : s.label ? COLORS.bear : COLORS.neutral, text: "",
      });
    }
  }
  if (t.structure) {
    for (const e of recent(events.filter((x) => x.kind === "BOS" || x.kind === "CHoCH"), visibleFrom, MAX_STRUCTURE)) {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: e.direction === "bullish" ? "arrowUp" : "arrowDown", color: dirColor(e.direction), text: e.kind });
    }
  }
  if (t.liquidity) {
    for (const e of recent(events.filter((x) => x.kind === "liquidity_sweep"), visibleFrom, MAX_SWEEPS)) {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: "square", color: COLORS.warn, text: "" });
    }
  }
  if (t.patterns) {
    for (const e of recent(events.filter((x) => ABBR[x.kind] && x.direction !== "neutral"), visibleFrom, MAX_PATTERNS)) {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: e.direction === "bullish" ? "arrowUp" : "arrowDown", color: dirColor(e.direction), text: ABBR[e.kind] });
    }
  }
  return out.sort((a, b) => a.time - b.time);
}

/** At most MAX_ZONES live (unmitigated) zones, nearest to the current price first, so they stay legible. */
export function buildZones(events: OverlayEvent[], t: OverlayToggles, visibleFrom = 0, ref?: { price: number; atr: number | null }): ChartZone[] {
  if (!t.zones) return [];
  const dist = (e: OverlayEvent) => {
    if (!ref) return 0;
    const lo = e.low as number, hi = e.high as number;
    return ref.price >= lo && ref.price <= hi ? 0 : Math.min(Math.abs(ref.price - lo), Math.abs(ref.price - hi));
  };
  const live = events.filter((e) => ZONE_KINDS.has(e.kind) && e.low !== null && e.high !== null && !(e.status && DEAD.has(e.status)) && e.ts >= visibleFrom);
  const near = ref?.atr ? live.filter((e) => dist(e) <= 8 * (ref.atr as number)) : live;
  return near
    .sort((a, b) => dist(a) - dist(b) || b.ts - a.ts)
    .slice(0, MAX_ZONES)
    .map((e) => ({
      from: e.start_ts ?? e.ts,
      low: e.low as number,
      high: e.high as number,
      color: rgba(dirColor(e.direction), e.kind === "fvg" ? 0.08 : 0.12),
      label: e.kind === "fvg" ? "FVG" : e.kind === "order_block" ? "OB" : e.kind === "breaker_block" ? "BB" : e.kind === "demand_zone" ? "Demand" : "Supply",
    }));
}

export function buildPlanLines(plan: TradePlan | null, t: OverlayToggles): ChartLine[] {
  if (!plan || !t.plan) return [];
  return [
    { price: plan.entry_ref, color: COLORS.primary, title: `${plan.direction} entry`, dashed: true },
    { price: plan.stop_loss, color: COLORS.bear, title: "SL" },
    ...plan.targets.map((p, i) => ({ price: p, color: COLORS.bull, title: `TP${i + 1}` })),
  ];
}

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
  bull: "#3fb97f",
  bear: "#ef5b64",
  neutral: "#8a94a6",
  warn: "#e5a93d",
  primary: "#4f9bf7",
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

export function buildMarkers(events: OverlayEvent[], swings: SwingPoint[], t: OverlayToggles, visibleFrom = 0): ChartMarker[] {
  const out: ChartMarker[] = [];
  if (t.swings) {
    for (const s of swings) {
      if (s.ts < visibleFrom) continue;
      out.push({
        time: s.ts, position: s.kind === "high" ? "aboveBar" : "belowBar", shape: "circle",
        color: s.label === "HH" || s.label === "HL" ? COLORS.bull : s.label ? COLORS.bear : COLORS.neutral, text: s.label ?? "",
      });
    }
  }
  for (const e of events) {
    if (e.ts < visibleFrom) continue;
    if (t.structure && (e.kind === "BOS" || e.kind === "CHoCH")) {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: e.direction === "bullish" ? "arrowUp" : "arrowDown", color: dirColor(e.direction), text: e.kind });
    } else if (t.liquidity && (e.kind === "liquidity_sweep" || e.kind === "equal_highs" || e.kind === "equal_lows")) {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: "square", color: COLORS.warn, text: e.kind === "liquidity_sweep" ? "Sweep" : "EQ" });
    } else if (t.patterns && ABBR[e.kind] && e.direction !== "neutral") {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: e.direction === "bullish" ? "arrowUp" : "arrowDown", color: dirColor(e.direction), text: ABBR[e.kind] });
    }
  }
  return out.sort((a, b) => a.time - b.time);
}

export function buildZones(events: OverlayEvent[], t: OverlayToggles, visibleFrom = 0): ChartZone[] {
  if (!t.zones) return [];
  return events
    .filter((e) => ZONE_KINDS.has(e.kind) && e.low !== null && e.high !== null && !(e.status && DEAD.has(e.status)) && e.ts >= visibleFrom - 86400 * 30)
    .map((e) => ({
      from: e.start_ts ?? e.ts,
      low: e.low as number,
      high: e.high as number,
      color: rgba(dirColor(e.direction), e.kind === "fvg" ? 0.1 : 0.16),
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

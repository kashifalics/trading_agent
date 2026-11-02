import type { OverlayEvent, SwingPoint, TradePlan } from "@/lib/types";
import type { ChartDetail, OverlayToggles } from "@/lib/store";
import { COLORS, type ChartLine, type ChartMarker, type ChartSegment, type ChartZone, dirColor, rgba } from "./overlays";

const ABBR: Record<string, string> = {
  bullish_engulfing: "Engulf", bearish_engulfing: "Engulf", hammer: "Hammer", shooting_star: "Star", pin_bar: "Pin",
  morning_star: "M.Star", evening_star: "E.Star",
};
const ZONE_KINDS = new Set(["fvg", "order_block", "breaker_block", "demand_zone", "supply_zone"]);
const DEAD = new Set(["filled", "invalidated", "broken", "mitigated"]);
const ZONE_LABEL: Record<string, string> = { fvg: "FVG", order_block: "OB", breaker_block: "Breaker", demand_zone: "Demand", supply_zone: "Supply" };

/** How much each layer shows. Clean = only what is near price and recent; Detailed = a fuller history. */
export const LIMITS: Record<ChartDetail, { structure: number; zones: number; zoneAtr: number; sweeps: number; patterns: number; patternBars: number; swings: number }> = {
  clean: { structure: 3, zones: 3, zoneAtr: 6, sweeps: 2, patterns: 3, patternBars: 40, swings: 6 },
  detailed: { structure: 10, zones: 8, zoneAtr: 20, sweeps: 8, patterns: 10, patternBars: 400, swings: 14 },
};

const recent = <T extends { ts: number }>(xs: T[], visibleFrom: number, n: number) => xs.filter((x) => x.ts >= visibleFrom).slice(-n);

/** BOS / CHoCH as the exact level that was broken: a thin line from the swing that set it to the bar whose close broke it. */
export function buildStructure(events: OverlayEvent[], t: OverlayToggles, visibleFrom = 0, detail: ChartDetail = "clean"): ChartSegment[] {
  if (!t.structure) return [];
  return recent(events.filter((e) => (e.kind === "BOS" || e.kind === "CHoCH") && e.price !== null && e.start_ts !== null), visibleFrom, LIMITS[detail].structure)
    .map((e) => ({
      from: e.start_ts as number, to: e.ts, price: e.price as number, color: dirColor(e.direction), dashed: e.kind === "BOS",
      label: `${e.kind} ${e.direction === "bullish" ? "▲" : "▼"}`, above: e.direction === "bullish",
    }));
}

/** Small, sparse markers: sweeps as dots, recent candle patterns as labelled arrows, optional swings. (Structure uses segments, not markers.) */
export function buildMarkers(events: OverlayEvent[], swings: SwingPoint[], t: OverlayToggles, visibleFrom = 0, detail: ChartDetail = "clean", lastTs = 0, barSeconds = 0): ChartMarker[] {
  const L = LIMITS[detail];
  const out: ChartMarker[] = [];
  if (t.swings) {
    for (const s of recent(swings, visibleFrom, L.swings)) {
      out.push({ time: s.ts, position: s.kind === "high" ? "aboveBar" : "belowBar", shape: "circle", color: s.label === "HH" || s.label === "HL" ? COLORS.bull : s.label ? COLORS.bear : COLORS.neutral, text: s.label ?? "" });
    }
  }
  if (t.liquidity) {
    for (const e of recent(events.filter((x) => x.kind === "liquidity_sweep"), visibleFrom, L.sweeps)) {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: "circle", color: COLORS.warn, text: detail === "detailed" ? "Sweep" : "" }); // Clean: a plain dot (the legend names it) so labels never pile up
    }
  }
  if (t.patterns) {
    const since = lastTs && barSeconds ? lastTs - L.patternBars * barSeconds : 0;
    for (const e of recent(events.filter((x) => ABBR[x.kind] && x.direction !== "neutral" && x.ts >= since), visibleFrom, L.patterns)) {
      out.push({ time: e.ts, position: e.direction === "bullish" ? "belowBar" : "aboveBar", shape: e.direction === "bullish" ? "arrowUp" : "arrowDown", color: dirColor(e.direction), text: ABBR[e.kind] });
    }
  }
  return out.sort((a, b) => a.time - b.time);
}

/** Live (unmitigated) zones near the current price, nearest first, capped per detail level. */
export function buildZones(events: OverlayEvent[], t: OverlayToggles, visibleFrom = 0, ref?: { price: number; atr: number | null }, detail: ChartDetail = "clean"): ChartZone[] {
  if (!t.zones) return [];
  const L = LIMITS[detail];
  const dist = (e: OverlayEvent) => {
    if (!ref) return 0;
    const lo = e.low as number, hi = e.high as number;
    return ref.price >= lo && ref.price <= hi ? 0 : Math.min(Math.abs(ref.price - lo), Math.abs(ref.price - hi));
  };
  const live = events.filter((e) => ZONE_KINDS.has(e.kind) && e.low !== null && e.high !== null && !(e.status && DEAD.has(e.status)) && e.ts >= visibleFrom);
  const near = ref?.atr ? live.filter((e) => dist(e) <= L.zoneAtr * (ref.atr as number)) : live;
  return near.sort((a, b) => dist(a) - dist(b) || b.ts - a.ts).slice(0, L.zones).map((e) => ({
    from: e.start_ts ?? e.ts, low: e.low as number, high: e.high as number,
    color: rgba(dirColor(e.direction), e.kind === "fvg" ? 0.1 : 0.16), border: rgba(dirColor(e.direction), 0.55),
    label: `${ZONE_LABEL[e.kind] ?? e.kind} ${e.direction === "bullish" ? "▲" : "▼"}`,
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

import { describe, expect, it } from "vitest";
import type { OverlayToggles } from "@/lib/store";
import type { OverlayEvent, TradePlan } from "@/lib/types";
import { buildMarkers, buildPlanLines, buildZones } from "./overlays";

const all: OverlayToggles = { swings: true, structure: true, zones: true, liquidity: true, patterns: true, plan: true };
const ev = (o: Partial<OverlayEvent>): OverlayEvent => ({
  kind: "fvg", direction: "bullish", time: "2024-01-01T00:00:00Z", start_time: null, ts: 1000, start_ts: 900,
  price: 10, low: 9, high: 11, status: "active", evidence: "x", ...o,
});

describe("chart overlays", () => {
  it("emits sorted markers and honours toggles", () => {
    const events = [ev({ kind: "BOS", ts: 300 }), ev({ kind: "liquidity_sweep", direction: "bearish", ts: 100 }), ev({ kind: "hammer", ts: 200 })];
    const swings = [{ kind: "high" as const, label: "HH", price: 5, ts: 150, confirm_ts: 180 }];
    const m = buildMarkers(events, swings, all);
    expect(m.map((x) => x.time)).toEqual([100, 150, 200, 300]);
    expect(buildMarkers(events, swings, { ...all, swings: false, patterns: false, liquidity: false })).toHaveLength(1);
  });

  it("keeps only the most recent few markers per layer and labels only structure breaks", () => {
    const many = Array.from({ length: 40 }, (_, i) => ev({ kind: "BOS", ts: 1000 + i }));
    const sweeps = Array.from({ length: 40 }, (_, i) => ev({ kind: "liquidity_sweep", ts: 2000 + i }));
    const swings = Array.from({ length: 40 }, (_, i) => ({ kind: "low" as const, label: "HL", price: 1, ts: 3000 + i, confirm_ts: 3003 + i }));
    const m = buildMarkers([...many, ...sweeps], swings, all);
    expect(m.length).toBeLessThanOrEqual(6 + 4 + 10);
    expect(m.filter((x) => x.text === "BOS").map((x) => x.time)).toEqual([1034, 1035, 1036, 1037, 1038, 1039]);
    expect(m.filter((x) => x.shape !== "arrowUp" && x.shape !== "arrowDown").every((x) => x.text === "")).toBe(true);
  });

  it("draws at most five live zones, nearest to the current price first", () => {
    const zones = [10, 20, 30, 40, 50, 60, 70].map((p, i) => ev({ kind: "order_block", low: p, high: p + 1, ts: 100 + i, status: "fresh" }));
    const z = buildZones([...zones, ev({ kind: "fvg", low: 11, high: 12, status: "filled" })], all, 0, { price: 41, atr: 100 });
    expect(z).toHaveLength(5);
    expect(z[0].low).toBe(40);
    expect(z.map((x) => x.low)).not.toContain(70);
    expect(buildZones(zones, all, 0, { price: 41, atr: 1 })).toHaveLength(1); // only zones within 8 ATR of price
  });

  it("draws only live zones (not filled / invalidated)", () => {
    const z = buildZones([ev({}), ev({ status: "filled" }), ev({ kind: "order_block", status: "invalidated" }), ev({ kind: "BOS" }), ev({ kind: "order_block", status: "fresh", direction: "bearish", low: 5, high: 6 })], all);
    expect(z.map((x) => x.label).sort()).toEqual(["FVG", "OB"]);
    expect(buildZones([ev({})], { ...all, zones: false })).toEqual([]);
  });

  it("builds entry / stop / target lines only for a real plan", () => {
    const plan: TradePlan = { direction: "BUY", entry_low: 99, entry_high: 101, entry_ref: 100, stop_loss: 98, invalidation: 98.5, targets: [104, 106], risk_reward: 2, target_basis: "fixed_multiple", warnings: [] };
    expect(buildPlanLines(plan, all).map((l) => l.title)).toEqual(["BUY entry", "SL", "TP1", "TP2"]);
    expect(buildPlanLines(null, all)).toEqual([]);
    expect(buildPlanLines(plan, { ...all, plan: false })).toEqual([]);
  });
});

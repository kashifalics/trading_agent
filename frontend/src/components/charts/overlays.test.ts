import { describe, expect, it } from "vitest";
import type { OverlayToggles } from "@/lib/store";
import type { OverlayEvent, TradePlan } from "@/lib/types";
import { LIMITS, buildMarkers, buildPlanLines, buildStructure, buildZones } from "./overlay-build";

const all: OverlayToggles = { swings: true, structure: true, zones: true, liquidity: true, patterns: true, plan: true };
const ev = (o: Partial<OverlayEvent>): OverlayEvent => ({
  kind: "fvg", direction: "bullish", time: "2024-01-01T00:00:00Z", start_time: null, ts: 1000, start_ts: 900,
  price: 10, low: 9, high: 11, status: "active", evidence: "x", ...o,
});

describe("chart overlays", () => {
  it("emits sorted markers for sweeps, patterns and swings and honours toggles (structure is drawn as segments, not markers)", () => {
    const events = [ev({ kind: "BOS", ts: 300 }), ev({ kind: "liquidity_sweep", direction: "bearish", ts: 100 }), ev({ kind: "hammer", ts: 200 })];
    const swings = [{ kind: "high" as const, label: "HH", price: 5, ts: 150, confirm_ts: 180 }];
    const m = buildMarkers(events, swings, all);
    expect(m.map((x) => x.time)).toEqual([100, 150, 200]);
    expect(buildMarkers(events, swings, { ...all, swings: false, patterns: false, liquidity: false })).toHaveLength(0);
  });

  it("draws BOS/CHoCH as the exact broken level from the swing bar to the breaking bar", () => {
    const seg = buildStructure([ev({ kind: "CHoCH", direction: "bearish", ts: 500, start_ts: 420, price: 3950.5 }), ev({ kind: "BOS", ts: 800, start_ts: 700, price: 3990 })], all);
    expect(seg).toEqual([
      expect.objectContaining({ from: 420, to: 500, price: 3950.5, label: "CHoCH ▼", dashed: false, above: false }),
      expect.objectContaining({ from: 700, to: 800, price: 3990, label: "BOS ▲", dashed: true, above: true }),
    ]);
    expect(buildStructure([ev({ kind: "BOS" })], { ...all, structure: false })).toEqual([]);
    expect(buildStructure([ev({ kind: "BOS", start_ts: null })], all)).toEqual([]); // no origin swing, no invented line
  });

  it("Clean shows far fewer items than Detailed, and only the most recent ones", () => {
    const bos = Array.from({ length: 40 }, (_, i) => ev({ kind: "BOS", ts: 1000 + i, start_ts: 900 + i }));
    expect(buildStructure(bos, all, 0, "clean").map((x) => x.to)).toEqual([1037, 1038, 1039]);
    expect(buildStructure(bos, all, 0, "detailed")).toHaveLength(LIMITS.detailed.structure);
    const sweeps = Array.from({ length: 40 }, (_, i) => ev({ kind: "liquidity_sweep", ts: 2000 + i }));
    const swings = Array.from({ length: 40 }, (_, i) => ({ kind: "low" as const, label: "HL", price: 1, ts: 3000 + i, confirm_ts: 3003 + i }));
    const clean = buildMarkers(sweeps, swings, all, 0, "clean");
    expect(clean.length).toBe(LIMITS.clean.sweeps + LIMITS.clean.swings);
    expect(buildMarkers(sweeps, swings, all, 0, "detailed").length).toBeGreaterThan(clean.length);
  });

  it("Clean patterns are only recent ones and carry a readable name", () => {
    const events = [ev({ kind: "bullish_engulfing", ts: 100 }), ev({ kind: "pin_bar", ts: 9000 }), ev({ kind: "doji", ts: 9100 })];
    const m = buildMarkers(events, [], all, 0, "clean", 10_000, 60); // last 40 bars = 2,400 s
    expect(m).toHaveLength(1);
    expect(m[0]).toMatchObject({ time: 9000, text: "Pin" });
    expect(buildMarkers(events, [], all, 0, "detailed", 10_000, 60).map((x) => x.text)).toEqual(["Engulf", "Pin"]);
  });

  it("shows only live zones near price, nearest first, capped per detail level", () => {
    const near = Array.from({ length: 8 }, (_, i) => ev({ ts: 1000 + i, low: 100 + i, high: 101 + i }));
    const dead = ev({ ts: 1100, low: 100, high: 101, status: "filled" });
    const far = ev({ ts: 1200, low: 500, high: 510 });
    const z = buildZones([...near, dead, far], all, 0, { price: 104, atr: 2 }, "clean");
    expect(z).toHaveLength(LIMITS.clean.zones);
    expect(z.every((x) => x.high < 200) && z[0].low <= 104 && z[0].high >= 104).toBe(true); // the zone containing price comes first
    expect(z[0]).toMatchObject({ label: "FVG ▲" });
    expect(z[0].border).toBeTruthy();
    expect(buildZones([...near, dead, far], all, 0, { price: 104, atr: 2 }, "detailed").length).toBeGreaterThan(z.length);
    expect(buildZones(near, { ...all, zones: false })).toEqual([]);
  });

  it("builds entry / stop / targets from a plan only when enabled", () => {
    const plan = { direction: "BUY", entry_low: 1, entry_high: 2, entry_ref: 1.5, stop_loss: 1, invalidation: 1, targets: [3, 4], risk_reward: 3, target_basis: "x", warnings: [] } as TradePlan;
    expect(buildPlanLines(plan, all).map((l) => l.title)).toEqual(["BUY entry", "SL", "TP1", "TP2"]);
    expect(buildPlanLines(plan, { ...all, plan: false })).toEqual([]);
    expect(buildPlanLines(null, all)).toEqual([]);
  });
});

import { describe, expect, it } from "vitest";
import { analysisSchema, backtestSchema, trainSchema, uploadSchema } from "@/lib/schemas";

describe("form schemas", () => {
  it("analysis: bounds the lookback and rejects unknown timeframes", () => {
    const ok = { symbol: "BTCUSDT", timeframe: "1H", lookback_bars: "1500", auto_sync: true };
    expect(analysisSchema.parse(ok).lookback_bars).toBe(1500);
    expect(analysisSchema.safeParse({ ...ok, lookback_bars: 50 }).success).toBe(false);
    expect(analysisSchema.safeParse({ ...ok, timeframe: "7m" }).success).toBe(false);
  });

  it("upload: calibration points are all-or-nothing and rows must differ", () => {
    expect(uploadSchema.safeParse({}).success).toBe(true);
    expect(uploadSchema.safeParse({ y1: "100", p1: "2400", y2: "500", p2: "2300" }).success).toBe(true);
    const partial = uploadSchema.safeParse({ y1: "100", p1: "2400" });
    expect(partial.success).toBe(false);
    expect(uploadSchema.safeParse({ y1: "100", p1: "2400", y2: "100", p2: "2300" }).success).toBe(false);
    expect(uploadSchema.safeParse({ timeframe: "9H" }).success).toBe(false);
  });

  it("backtest and train: numeric coercion and limits", () => {
    const bt = backtestSchema.parse({ symbol: "BTCUSDT", timeframe: "1H", strategy: "ma_cross", bars: "3000", risk_pct: "1", spread: "0", slippage: "0", commission_pct: "0", eval_every: "2" });
    expect(bt.bars).toBe(3000);
    expect(backtestSchema.safeParse({ ...bt, risk_pct: 25 }).success).toBe(false);
    expect(backtestSchema.safeParse({ ...bt, risk_pct: 0 }).success).toBe(false);
    expect(trainSchema.safeParse({ symbol: "BTCUSDT", timeframe: "1H", algorithm: "svm", bars: 5000, spread: 0, horizon_bars: 24 }).success).toBe(false);
  });
});

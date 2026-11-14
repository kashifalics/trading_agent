// Strategy-engine v2 API fixtures shaped like backend output (TEST DATA ONLY: illustrative prices, never real signals).
import type { Confirmation, EngineItem, EnginePlan, EngineSummary, EngineTimeframe, SignalRecord, Verdict } from "@/lib/engine-types";

const NOW = new Date().toISOString();

const ORDER = ["regime", "htf", "entry", "structure", "vsa", "momentum", "trend", "volatility", "execution", "rr"] as const;
const LABEL: Record<string, string> = { regime: "Market regime", htf: "Higher timeframe", entry: "Entry", structure: "Market structure", vsa: "VSA",
  momentum: "Momentum", trend: "Trend", volatility: "Volatility", execution: "Spread & execution", rr: "Risk/reward" };
const EVIDENCE = ["vsa", "momentum", "trend", "volatility"];

/** The ten components of the confirmation matrix, PASS unless overridden; `gates` = categories promoted by Experiment 6. */
export const conf = (verdicts: Partial<Record<string, [Verdict, string]>> = {}, gates: string[] = []): Confirmation[] =>
  ORDER.map((key) => {
    const [verdict, reason] = verdicts[key] ?? (["PASS", `${LABEL[key]} ok`] as [Verdict, string]);
    const mandatory = !EVIDENCE.includes(key);
    const gating = gates.includes(key);
    return { key, label: LABEL[key], verdict, reason, evidence: key === "momentum" ? { macd_hist: 0.12, rsi: 55 } : {}, mandatory, gating,
      promoted_by: gating ? "Experiment 6" : null, note: mandatory ? "" : gating ? "gate: Experiment 6" : "evidence only — not tested" };
  });

export const regime = (label: EngineTimeframe["regime"]["label"], name: string, direction = 0) => ({
  label, name, direction, subtype: label === "UNKNOWN" ? "transitional" : null, reason: `${name} regime`, metrics: {}, criteria: [], criteria_met: 0,
});

export const plan = (over: Partial<EnginePlan> = {}): EnginePlan => ({
  entry_mode: "market", entry: 3915.29, entry_zone: null, stop_loss: 3906.83, risk: 8.46, risk_atr: 1.1,
  targets: [
    { label: "TP1", price: 3942.4, rr: 3.2, rr_net: 3.16, basis: "swing high" },
    { label: "TP2", price: 3961.8, rr: 5.5, rr_net: 5.46, basis: "previous day high" },
    { label: "TP3", price: 3981.0, rr: 7.77, rr_net: 7.73, basis: "risk objective 7.8R" },
  ],
  risk_reward: 3.2, spread: 0.3, cost_r: 0.04, invalidation: 3907.6, invalidation_text: "a 1H close below 3,907.60", entry_status: "READY",
  trigger: "continuation close beyond the pullback high 3,913.10: enter at market", signal_time: NOW, expires_at: NOW, price_now: 3915.5, ...over,
});

const opp = (over: Partial<EngineTimeframe>): NonNullable<EngineItem["opportunity"]> => ({
  timeframe: "1H", group: "intraday", context_tf: "4H", regime: regime("TRENDING", "Trending up", 1), context_regime: null, action: "BUY",
  direction: "BUY", strategy: "trend_pullback", strategy_name: "Trend-following pullback", technical_status: "QUALIFIED",
  research_status: "INSUFFICIENT EVIDENCE", plan_label: "UNVALIDATED — HYPOTHETICAL TRADE PLAN", plan: plan(),
  why: ["uptrend: ADX 31, ER 0.42", "pullback to EMA20 (3,910.20)", "momentum recovered (RSI crossed 50)"], missing: [],
  next_action: "BUY now near 3,915.29 (skip it if price runs more than 0.3R past the entry); stop 3,906.83, TP1 3,942.40.",
  headline: "BUY: Trend-following pullback on 1H (trending up)", agreeing: [], conflict: null, n_bars: 272, data_time: NOW, ...over,
});

const tfs = (action: EngineTimeframe["action"]) => ["1m", "3m", "5m", "15m", "30m", "1H", "4H", "8H", "1D", "1W", "1M"].map((tf) => ({
  timeframe: tf, action: tf === "1H" ? action : ("NO TRADE" as const), strategy_name: tf === "1H" && action !== "NO TRADE" ? "Trend-following pullback" : null,
  regime: "UNKNOWN" as const, regime_name: "Unknown", entry_status: null, risk_reward: tf === "1H" && action !== "NO TRADE" ? 3.2 : null, headline: "x",
}));

const base = (symbol: string, over: Partial<EngineItem>): EngineItem => ({
  symbol, name: symbol, status: "ok", price_precision: 2, price_now: 100, price_source: "live quote", data_time: NOW, generated_at: NOW,
  market_open: true, session: { label: "London", entry_allowed: true, block_reason: null }, primary: { action: "NO TRADE", kind: "no_trade", headline: "" },
  opportunity: null, exits: [], risk: null, tfs: tfs("NO TRADE"), trades: [], ...over,
});

export const GOLD_BUY = base("XAUUSD", {
  name: "Gold / US Dollar (spot)", price_now: 3915.5, primary: { action: "BUY", kind: "opportunity", headline: "BUY: Trend-following pullback on 1H", timeframe: "1H" },
  opportunity: opp({
    confirmations: conf({ vsa: ["UNAVAILABLE", "VSA unavailable: zero or missing volume on 12% of recent candles"],
      momentum: ["NEUTRAL", "MACD histogram mixed over the last 2 candles"] }),
    volume: { type: "tick", label: "Tick volume (broker)", reliable: false, reason: "zero or missing volume on 12% of recent candles" },
    vsa: { events: [], pressure: { source: "inferred from price", value: 0.81, side: "buying" }, context: null },
  }), tfs: tfs("BUY"),
});

export const EUR_WAIT_SELL = base("EURUSD", {
  price_precision: 5, price_now: 1.10877,
  primary: { action: "WAIT FOR SELL", kind: "opportunity", headline: "WAIT FOR SELL: Breakout and retest on 4H", timeframe: "4H" },
  opportunity: opp({
    timeframe: "4H", action: "WAIT FOR SELL", direction: "SELL", strategy: "breakout_retest", strategy_name: "Breakout and retest",
    regime: regime("RANGING", "Ranging"), plan: plan({ entry_mode: "limit", entry: 1.11012, entry_zone: [1.10994, 1.11012], stop_loss: 1.1121, risk: 0.00198,
      targets: [{ label: "TP1", price: 1.1071, rr: 1.53, rr_net: 1.5, basis: "swing low" }, { label: "TP2", price: 1.10418, rr: 3.0, rr_net: 2.97, basis: "risk objective 3R" },
        { label: "TP3", price: 1.10022, rr: 5.0, rr_net: 4.97, basis: "risk objective 5R" }], risk_reward: 1.53, entry_status: "WAITING FOR ENTRY",
      invalidation_text: "a 4H close above 1.11180", trigger: "SELL limit at 1.11012 on a retest of the broken level 1.10994" }),
    next_action: "SELL limit at 1.11012 on a retest of the broken level 1.10994. Cancel if a 4H close above 1.11180 or after 20 4H candles.",
    missing: ["missing confirmation: momentum (MACD histogram rising 2 candles in a row, against the trade)"],
    confirmations: conf({ momentum: ["FAIL", "MACD histogram rising 2 candles in a row, against the trade"],
      vsa: ["PASS", "breakout on 1.80x volume, retest on 0.70x"] }, ["momentum"]),
    volume: { type: "tick", label: "Tick volume (broker)", reliable: true, reason: "" },
    vsa: { events: [{ kind: "no_demand", time: NOW, direction: -1, state: "n/a", text: "no demand: narrow up candle on falling volume (0.6x) in a rally" }],
      pressure: { source: "inferred from price", value: 0.2, side: "selling" }, context: null },
  }),
  tfs: tfs("WAIT FOR SELL"),
});

export const GBP_NO_TRADE = base("GBPUSD", {
  price_precision: 5, price_now: 1.32673,
  primary: { action: "NO TRADE", kind: "no_trade", headline: "NO TRADE: no strategy qualifies on any timeframe",
    why: ["no strategy qualifies on 1H (range: ADX 14)", "only 101 complete candles (at least 120 needed)"] },
});

export const US30_EXIT = base("US30", {
  price_precision: 1, price_now: 51780,
  primary: { action: "EXIT", kind: "exit", headline: "EXIT the tracked paper BUY trade on 3m",
    exit: { trade_id: 7, timeframe: "3m", status: "open", direction: "BUY", action: "EXIT", reason: "Price 51,780.0 is at or beyond the stop-loss 51,788.8.",
      exit_kind: "stop_loss", entry_price: 51841, current_price: 51780, stop_loss: 51788.8, take_profit: 53001.1, stop_distance: 0, target_distance: 1221,
      unrealized_r: -1.2, unrealized_pnl: null } },
  opportunity: opp({ timeframe: "15m", action: "WAIT FOR BUY", direction: "BUY", strategy: "sweep_reversal", strategy_name: "Liquidity-sweep reversal",
    regime: regime("UNKNOWN", "Unknown"), plan: plan({ entry_mode: "limit", entry: 51790, stop_loss: 51700, risk: 90, entry_status: "WAITING FOR ENTRY",
      targets: [{ label: "TP1", price: 51935, rr: 1.61, rr_net: 1.58, basis: "swing high" }, { label: "TP2", price: 52060, rr: 3.0, rr_net: 2.97, basis: "risk objective 3R" },
        { label: "TP3", price: 52240, rr: 5.0, rr_net: 4.97, basis: "risk objective 5R" }], risk_reward: 1.61 }) }),
  trades: [{ id: 7, timeframe: "3m", direction: "BUY", status: "open", fill_price: 51841, entry_price: 51841, stop_loss: 51788.8, take_profit: 53001.1,
    last_price: 51780, unrealized_r: -1.2 }],
});

export const ENGINE_SUMMARY: EngineSummary = {
  items: [US30_EXIT, GOLD_BUY, EUR_WAIT_SELL, GBP_NO_TRADE], generated_at: NOW, engine_version: "v2-test",
  research_note: "Not tested yet: the experiment plan awaits approval.", news: { available: false, note: "High-impact news is NOT filtered." },
};

export const RECORD: SignalRecord = {
  id: 11, symbol: "XAUUSD", timeframe: "1H", strategy: "trend_pullback", strategy_name: "Trend-following pullback", direction: "BUY", regime: "TRENDING",
  entry_mode: "market", entry: 3915.29, stop_loss: 3906.83, tp1: 3942.4, tp2: 3961.8, tp3: 3981.0, status: "TP1 HIT", research_status: "INSUFFICIENT EVIDENCE",
  signal_time: NOW, detected_at: NOW, closed_at: null, best_target: 1, last_price: 3944,
  history: [{ status: "DETECTED", at: NOW, price: 3915.5, note: "" }, { status: "ACTIVE", at: NOW, price: 3915.29, note: "" }, { status: "TP1 HIT", at: NOW, price: 3942.4, note: "" }],
  hypothetical: true,
};

import type { TradeCall } from "@/lib/decision-types";
import type { Analysis, Instrument, Quote } from "@/lib/types";
import { CALL_PRED_BUY, CALL_PRED_WAIT } from "@/test/calls";

const inst = (id: number, sym: string, name: string, supported: boolean, provider: string, status: "active" | "unverified" | "unsupported", prec = 2): Instrument => ({
  id, canonical_symbol: sym, name, asset_class: "x", quote_currency: "USD", price_precision: prec, tick_size: 0.01, calendar: "continuous",
  session_tz: "UTC", trading_session: null, supported,
  mappings: [{ provider, provider_symbol: sym, exchange: null, market_kind: "spot", status, notes: status === "unsupported" ? "No licensed feed configured." : null }],
});

export const INSTRUMENTS: Instrument[] = [
  inst(1, "XAUUSD", "Gold / US Dollar", true, "twelve_data", "unverified"),
  inst(2, "US30", "Dow Jones", false, "broker_cfd", "unsupported", 1),
  inst(3, "BTCUSDT", "Bitcoin / Tether", true, "binance", "active"),
  inst(4, "USOIL", "WTI Crude", false, "broker_cfd", "unsupported"),
];

export const QUOTES: Quote[] = [
  { symbol: "XAUUSD", status: "not_configured", price: null, bid: null, ask: null, time: null, provider: null, message: "TWELVE_DATA_API_KEY is not set" },
  { symbol: "US30", status: "unsupported", price: null, bid: null, ask: null, time: null, provider: null, message: "US30 is unsupported until a data source is configured." },
  { symbol: "BTCUSDT", status: "ok", price: 77488.745, bid: 77488.74, ask: 77488.75, time: new Date().toISOString(), provider: "binance", message: null },
  { symbol: "USOIL", status: "unsupported", price: null, bid: null, ask: null, time: null, provider: null, message: "USOIL is unsupported until a data source is configured." },
];

export const CANDLES = {
  symbol: "BTCUSDT", timeframe: "1H", provider: "binance", price_precision: 2, count: 3,
  candles: [1, 2, 3].map((i) => ({ time: 1_700_000_000 + i * 3600, open: 100 + i, high: 102 + i, low: 99 + i, close: 101 + i, volume: 1, complete: true, origin: "native" })),
};

const conf = {
  model_probability: null, research_only_model_output: null, historical_frequency: null,
  analytical_confluence: { score: 0.55, scale: "[-1, +1]", components: [] }, data_quality: { score: 0.9, issues: [] }, uncertainty: [],
};

export const analysis = (decision: "BUY" | "WAIT", status: Analysis["status"] = "completed", call?: TradeCall): Analysis => ({
  id: 7, instrument_id: 3, symbol: "BTCUSDT", timeframe: "1H", source: "market_data", status, params: null, error: null,
  call: status !== "completed" ? null : call ?? (decision === "BUY" ? CALL_PRED_BUY : CALL_PRED_WAIT),
  as_of_ts: "2026-10-31T20:00:00Z", created_at: "2026-10-31T20:00:00Z", completed_at: null, prediction_id: 9,
  result: status !== "completed" ? null : {
    events: [], swings: [], analogues: null, mtf: null, atr: 1, last_close: 104, bars_used: 700, model: null,
    decision: {
      decision, confluence: decision === "BUY" ? 0.55 : 0.1, evidence: [], as_of: "2026-10-31T20:00:00Z", confidence: conf, warnings: [],
      explanation: decision === "BUY" ? "BUY setup on BTCUSDT 1H" : "WAIT on BTCUSDT 1H",
      wait_reasons: decision === "WAIT" ? ["confluence +0.10 is below the +/-0.35 threshold (weak evidence)"] : [],
      plan: decision === "BUY" ? { direction: "BUY", entry_low: 103.5, entry_high: 104.5, entry_ref: 104, stop_loss: 101, invalidation: 101.5, targets: [110, 113], risk_reward: 2, target_basis: "fixed_multiple", warnings: [] } : null,
    },
  },
});

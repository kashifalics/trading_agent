// Types for /api/v1/signals (backend: app/signals, docs/SIGNAL_ENGINE.md).

export type SignalState =
  | "NO_SETUP"
  | "WATCHLIST"
  | "SETUP_DEVELOPING"
  | "WAITING_FOR_CONFIRMATION"
  | "ENTRY_READY"
  | "TRADE_INVALIDATED"
  | "TRADE_EXPIRED";

export type Instruction = "EXECUTE NOW" | "WAIT FOR CONFIRMATION" | "PLACE LIMIT ORDER" | "NO TRADE";
export type Side = "BUY" | "SELL";

export interface ScoreCheck {
  key: string;
  label: string;
  max: number;
  points: number;
  met: boolean;
  detail: string;
}

export interface ScoreFactor {
  key: string;
  label: string;
  max: number;
  points: number;
  checks: ScoreCheck[];
}

export interface PlanTarget {
  label: string;
  price: number;
  rr: number;
  basis: string;
}

export interface MarketRead {
  timeframe: string;
  class: string;
  label: string;
  direction: number;
  structure: string | null;
  observation: string;
  last_event: string | null;
  zone: string | null;
  range_position: number | null;
  last_close: number;
  atr: number | null;
}

export interface TrackRecordRef {
  available: boolean;
  status: "validated" | "no_edge" | "negative" | "untested";
  summary: string;
  win_probability: number | null;
  win_probability_basis?: string;
  period?: { start: string; oos_start: string; end: string } | null;
  oos?: {
    n_trades: number | null;
    tp1_hit_rate: number | null;
    expectancy_r: number | null;
    profit_factor: number | null;
    expectancy_r_ci_low: number | null;
    expectancy_r_ci_high: number | null;
  };
  buckets?: Record<string, { n: number; tp1_hit_rate: number | null; expectancy_r: number | null }> | null;
}

export interface TimeframePlan {
  timeframe: string;
  group: string;
  group_label: string;
  bias_tfs: string[];
  confirm_tf: string;
  status: "ok" | "insufficient_data" | "stale";
  state: SignalState;
  instruction: Instruction;
  decision: Side | "WAIT" | "NO TRADE";
  direction: Side | null;
  side?: Side;
  score: number | null;
  signal_class?: string;
  confluence_band?: string;
  grade: "A" | "B" | null;
  buy_score: number | null;
  sell_score: number | null;
  reason?: string;
  setup_type?: string;
  entry_type?: "market" | "limit";
  entry?: number;
  entry_zone?: [number, number] | null;
  zone_kind?: string | null;
  stop_loss?: number;
  invalidation?: number;
  targets: PlanTarget[];
  risk_reward?: number;
  risk?: number;
  risk_atr?: number;
  atr?: number;
  cost_r?: number;
  spread?: number;
  factors: ScoreFactor[];
  checks_met?: number;
  checks_total?: number;
  reasons_for: string[];
  reasons_against: string[];
  conditions: string[];
  warnings: string[];
  blocked: string[];
  reasoning?: { entry: string; stop: string; targets: string[] };
  summary?: string;
  signal_time?: string;
  valid_until?: string;
  as_of?: string;
  market: MarketRead | null;
  bias?: { timeframe: string; label: string; direction: number | null; structure: string | null; observation: string | null }[];
  other_side?: { direction: Side; score: number | null; state?: SignalState; reason?: string };
  previous?: { side: Side; entry: number; stop_loss: number; state: SignalState; reason: string };
  probability_note: string;
  win_probability: number | null;
  track_record?: TrackRecordRef;
}

export interface TimeframeRow {
  timeframe: string;
  status: string;
  n_bars: number;
  reason?: string;
  stale_bars?: number | null;
  derived_from?: string | null;
  class?: string;
  label?: string;
  direction?: number;
  structure?: string | null;
  observation?: string;
  last_event?: string | null;
  zone?: string | null;
  last_close?: number;
  close_time?: string;
}

export interface Overall {
  label: "Bullish" | "Bearish" | "Mixed";
  score: number;
  direction: number;
  detail: string;
  groups: Record<string, string>;
}

export interface QuoteInfo {
  price: number;
  bid: number | null;
  ask: number | null;
  spread: number | null;
  time: string;
  delayed: boolean;
  provider: string;
}

export interface SignalAnalysis {
  symbol: string;
  name?: string;
  status: "ok" | "unavailable";
  reason?: string;
  provider: string;
  provider_status?: string;
  price_precision: number;
  generated_at: string;
  config_version: string;
  market_open?: boolean;
  quote?: QuoteInfo | null;
  spread_model?: number | null;
  overall: Overall | null;
  timeframes: TimeframeRow[];
  plans: TimeframePlan[];
  active: string[];
  watchlist: string[];
  best: TimeframePlan | null;
  counts: { entry_ready: number; waiting: number; developing: number; watchlist: number; no_setup: number } | null;
  session?: string | null;
  news_filter?: { available: boolean; note: string };
  report?: { final_instruction: Instruction; text: string } | null;
  analysis_report?: { final_decision: string; signal_class?: string; confluence_band?: string; market_regime?: string | null } | null;
  disclaimer: string;
}

export interface CompactPlan {
  timeframe: string;
  state: SignalState;
  instruction: Instruction;
  decision: string;
  direction: Side | null;
  score: number | null;
  signal_class?: string;
  confluence_band?: string;
  grade: "A" | "B" | null;
  setup_type?: string;
  entry_type?: string;
  entry?: number;
  stop_loss?: number;
  tp1: number | null;
  risk_reward?: number;
  summary?: string;
}

export interface SignalsSummaryItem {
  symbol: string;
  name?: string;
  status: "ok" | "unavailable" | "failed";
  reason?: string;
  provider?: string;
  price_precision?: number;
  market_open?: boolean;
  quote?: QuoteInfo | null;
  overall?: Overall | null;
  counts?: SignalAnalysis["counts"];
  session?: string | null;
  best?: CompactPlan | null;
  active?: CompactPlan[];
  last_candle?: string | null;
}

export interface SignalsSummary {
  items: SignalsSummaryItem[];
  generated_at: string;
  config_version: string;
  disclaimer: string;
}

export interface SignalSync {
  synced: boolean;
  provider: string;
  fetched?: string[];
  notes: string[];
  analysis: SignalAnalysis;
}

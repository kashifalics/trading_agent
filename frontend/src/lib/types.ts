// Mirrors the backend OpenAPI schemas (backend/app/schemas). Keep in sync with /openapi.json.

export type Decision = "BUY" | "SELL" | "WAIT";
export type JobStatus = "queued" | "running" | "completed" | "failed";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Mapping {
  provider: string;
  provider_symbol: string;
  exchange: string | null;
  market_kind: string;
  status: "active" | "unverified" | "unsupported";
  notes: string | null;
}

export interface Instrument {
  id: number;
  canonical_symbol: string;
  name: string;
  asset_class: string;
  quote_currency: string;
  price_precision: number;
  tick_size: number | null;
  calendar: string;
  session_tz: string;
  trading_session: string | null;
  mappings: Mapping[];
  supported: boolean;
}

export interface Timeframe {
  code: string;
  label: string;
  seconds: number | null;
  months: number | null;
  native_on: string[];
}

export interface Candle {
  time: number; // UTC epoch seconds, candle open
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  complete: boolean;
  origin: string;
}

export interface CandlesResponse {
  symbol: string;
  timeframe: string;
  provider: string;
  price_precision: number;
  count: number;
  candles: Candle[];
}

export interface GapInfo {
  start: string;
  end: string;
  missing: number;
}

export interface Coverage {
  instrument: string;
  provider: string;
  timeframe: string;
  first_ts: string | null;
  last_ts: string | null;
  candle_count: number;
  gap_count: number;
  gaps: GapInfo[];
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_error: string | null;
}

export interface Quote {
  symbol: string;
  status: "ok" | "unsupported" | "not_configured" | "error";
  price: number | null;
  bid: number | null;
  ask: number | null;
  time: string | null;
  provider: string | null;
  message: string | null;
  /** Last known price (market closed or quote stale): never shown as live. */
  delayed?: boolean;
}

export interface ProviderInfo {
  code: string;
  name: string;
  requires_api_key: boolean;
  status: "configured" | "needs_api_key" | "no_adapter";
  free_plan: Record<string, unknown> | null;
  licensing: string | null;
  docs_url: string | null;
  signup_url: string | null;
  note: string | null;
  instruments: { symbol: string; provider_symbol: string; status: string; market_kind: string; notes: string | null }[];
}

export interface OverlayEvent {
  kind: string;
  direction: "bullish" | "bearish" | "neutral";
  time: string;
  start_time: string | null;
  ts: number;
  start_ts: number | null;
  price: number | null;
  low: number | null;
  high: number | null;
  status: string | null;
  evidence: string;
}

export interface SwingPoint {
  kind: "high" | "low";
  label: string | null;
  price: number;
  ts: number;
  confirm_ts: number;
}

export interface EvidenceItem {
  category: string;
  name: string;
  direction: "bullish" | "bearish" | "neutral";
  weight: number;
  score: number;
  detail: string | null;
  ts: string | null;
  price: number | null;
}

export interface TradePlan {
  direction: "BUY" | "SELL";
  entry_low: number;
  entry_high: number;
  entry_ref: number;
  stop_loss: number;
  invalidation: number;
  targets: number[];
  risk_reward: number;
  target_basis: string;
  warnings: string[];
}

export interface Freq {
  k: number;
  n: number;
  frequency: number | null;
  ci_low: number | null;
  ci_high: number | null;
}

export interface ConfidencePanel {
  model_probability: { p_long_tp_first: number; p_short_tp_first: number; p_neither: number; model_version_id: number | null } | null;
  research_only_model_output: {
    p_long_tp_first: number;
    p_short_tp_first: number;
    p_neither: number;
    validation_status: string | null;
    note: string;
  } | null;
  historical_frequency: {
    long_tp_before_sl: Freq;
    short_tp_before_sl: Freq;
    base_rate_long: Freq;
    base_rate_short: Freq;
    n_obs: number;
    sufficient: boolean;
    label: string;
  } | null;
  analytical_confluence: {
    score: number | null;
    scale: string;
    components: { name: string; weight: number; score: number; contribution: number }[];
  };
  data_quality: { score: number; issues: string[] };
  uncertainty: string[];
}

export interface DecisionResult {
  decision: Decision;
  confluence: number | null;
  evidence: EvidenceItem[];
  wait_reasons: string[];
  warnings: string[];
  plan: TradePlan | null;
  confidence: ConfidencePanel;
  explanation: string;
  as_of: string | null;
}

export interface AnalogueSummary {
  query_idx: number;
  n_library: number;
  n_obs: number;
  sufficient: boolean;
  reason: string | null;
  note: string;
  stats: {
    horizon_bars: number;
    tp_atr: number;
    sl_atr: number;
    long_tp_before_sl: Freq;
    short_tp_before_sl: Freq;
    base_rate_long: Freq;
    base_rate_short: Freq;
    timeout_or_ambiguous: Freq;
    forward_return: {
      n: number;
      unit?: string;
      mean_ci?: { mean: number; ci_low: number; ci_high: number } | null;
      quantiles?: Record<string, number>;
      share_positive?: number;
    };
    excursions: { n: number; mfe_mean?: number; mae_mean?: number; mfe_median?: number; mae_median?: number };
    mean_similarity: number;
  } | null;
}

export interface MtfView {
  timeframe: string;
  role: string;
  direction: number;
  note: string;
  zone: string | null;
}

export interface AnalysisResult {
  decision: DecisionResult;
  events: OverlayEvent[];
  swings: SwingPoint[];
  analogues: AnalogueSummary | null;
  mtf: { score: number; aligned: boolean; conflict: boolean; views: MtfView[]; available: boolean } | null;
  atr: number | null;
  last_close: number;
  bars_used: number;
  model: Record<string, unknown> | null;
}

export interface Analysis {
  id: number;
  instrument_id: number;
  symbol: string | null;
  timeframe: string;
  source: string;
  status: JobStatus;
  params: Record<string, unknown> | null;
  result: AnalysisResult | null;
  error: string | null;
  as_of_ts: string | null;
  created_at: string;
  completed_at: string | null;
  prediction_id: number | null;
}

export interface JobAccepted {
  id: number;
  status: JobStatus;
  poll_url: string;
}

export interface Prediction {
  id: number;
  analysis_id: number;
  symbol: string | null;
  provider_code: string | null;
  timeframe: string;
  decision: Decision;
  entry_low: number | null;
  entry_high: number | null;
  stop_loss: number | null;
  take_profit: number[] | null;
  risk_reward: number | null;
  invalidation_level: number | null;
  model_version_id: number | null;
  probabilities: Record<string, number> | null;
  confluence_score: number | null;
  data_quality_score: number | null;
  warnings: string[] | null;
  explanation: string | null;
  as_of_ts: string;
  outcome: "open" | "tp_hit" | "sl_hit" | "expired" | "not_applicable" | "not_filled";
  outcome_ts: string | null;
  outcome_meta: Record<string, unknown> | null;
  created_at: string;
}

export interface PredictionDetail extends Prediction {
  evidence: EvidenceItem[];
  confidence: ConfidencePanel | null;
  wait_reasons: string[];
}

export interface PredictionStats {
  total: number;
  by_decision: Record<string, number>;
  by_outcome: Record<string, number>;
  resolved: number;
  tp_first_rate: number | null;
  tp_first_ci: [number, number] | null;
  per_instrument: Record<string, { total: number; BUY: number; SELL: number; WAIT: number; tp_hit: number; sl_hit: number; avg_r: number | null }>;
  note: string;
}

export interface AnaloguesResponse {
  analysis_id: number;
  status: string;
  summary: AnalogueSummary | null;
  note: string;
  analogues: {
    rank: number;
    time: string;
    similarity: number;
    horizon_bars: number;
    forward_return_atr: number | null;
    mfe_atr: number | null;
    mae_atr: number | null;
    long_tp_before_sl: boolean | null;
    short_tp_before_sl: boolean | null;
  }[];
}

export interface PatternsResponse {
  symbol: string;
  timeframe: string;
  provider: string;
  n_bars: number;
  events: OverlayEvent[];
  swings: SwingPoint[];
  counts?: Record<string, number>;
  structure_trend?: number;
  atr?: number | null;
  message?: string;
}

export interface PatternDefinitions {
  candlestick: Record<string, string>;
  price_action: Record<string, string>;
  note: string;
}

export interface BacktestTrade {
  direction: "BUY" | "SELL";
  signal_ts: string;
  entry_ts: string;
  entry_price: number;
  exit_ts: string;
  exit_price: number;
  exit_reason: string;
  stop_loss: number;
  take_profit: number | null;
  units: number;
  pnl: number;
  r_multiple: number;
  costs: number;
}

export interface Backtest {
  id: number;
  symbol: string | null;
  timeframe: string;
  strategy: string;
  status: JobStatus;
  config: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  equity_curve: [string, number][] | null;
  start_ts: string | null;
  end_ts: string | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  trades: BacktestTrade[];
}

export interface ModelRow {
  id: number;
  name: string;
  algorithm: string;
  symbol: string | null;
  timeframe: string;
  version: string;
  trained_at: string;
  n_samples: number;
  validation_status: string;
  validation_reasons: string[] | null;
  is_calibrated: boolean;
  is_active: boolean;
  summary: { n_oos_rows: number | null; brier: number | null; brier_baseline: number | null; brier_skill: number | null; prediction_coverage: number | null; error: string | null };
  oos_trades: Record<string, number | null> | null;
}

export interface Watchlist {
  id: number;
  name: string;
  created_at: string;
  items: { id: number; symbol: string; note: string | null }[];
}

export interface Health {
  status: string;
  version: string;
  env: string;
  time: string;
  mode: string;
  components: Record<string, string | boolean>;
  /** True when every request needs a platform API key (X-API-Key). */
  auth_required?: boolean;
}

export interface AuthStatus {
  authenticated: boolean;
  auth_required: boolean;
  mode: string;
  key_used: boolean;
}

export interface ChartAnalyzeResult {
  extraction_id: number;
  status: "extracted" | "needs_input" | "analysed" | "failed";
  symbol: string | null;
  timeframe: string | null;
  n_candles: number;
  price_calibrated: boolean;
  quality: { score: number; usable: boolean; ocr_available: boolean; breakdown: Record<string, number> };
  warnings: string[];
  analysis_id: number | null;
  prediction_id: number | null;
  data_source?: string;
}

export type EvidenceVerdict =
  | "confirmed_tradeable"
  | "confirmed_not_profitable_after_costs"
  | "failed_out_of_sample"
  | "no_edge_found"
  | "too_few_events"
  | "no_study_data";

export interface PatternEvidence {
  i_n: number | null;
  i_lift: number | null;
  o_n: number | null;
  o_win: number | null;
  o_gross: number | null;
  o_net: number | null;
  o_lift: number | null;
  o_holm: number | null;
  cand?: boolean;
  cg?: boolean;
  cn?: boolean;
}

export interface PatternFiring {
  pattern: string;
  side: "long" | "short";
  bars_ago: number;
  verdict: EvidenceVerdict;
  evidence: PatternEvidence | null;
}

export interface ScanFrame {
  timeframe: string;
  bars: number;
  status: "ok" | "insufficient_data";
  structure_trend?: number;
  last_break?: string | null;
  zone?: string | null;
  range_position?: number | null;
  atr?: number | null;
  last_close?: number;
  live_zones?: number;
  patterns_firing?: PatternFiring[];
}

export interface PatternScan {
  symbol: string;
  provider: string;
  recent_bars: number;
  timeframes: ScanFrame[];
  alignment: { bullish_timeframes: number; bearish_timeframes: number; analysed: number };
  evidence_meta: Record<string, unknown>;
  note: string;
}

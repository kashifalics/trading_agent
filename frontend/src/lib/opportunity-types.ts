// Types for the Trade Opportunities module (GET/POST /api/v1/opportunities/*). They mirror the backend payloads exactly.

export type OppStyle = "scalping" | "intraday" | "swing" | "long_term";
export type OppDirection = "BUY" | "SELL" | "WAIT";
export type OppStatus = "none" | "watchlist" | "waiting_for_confirmation" | "entry_triggered" | "invalidated" | "expired";
export type ValidationStatus = "validated" | "untested" | "no_edge" | "negative";
export type TfStatus = "completed" | "running" | "insufficient_data" | "unsupported" | "failed";

export interface Opportunity {
  id: number;
  symbol: string;
  style: OppStyle;
  is_headline: boolean;
  scan_id: number;
  last_scan_id: number;
  direction: OppDirection;
  status: OppStatus;
  setup_timeframe: string | null;
  setup_type: string | null;
  risk_reward: number | null;
  evidence_score: number | null;
  validation_status: ValidationStatus | null;
  expected_holding_seconds: number | null;
  entry_low: number | null;
  entry_high: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  take_profit_3: number | null;
  invalidation: number | null;
  side: "BUY" | "SELL" | null; // direction of the underlying setup, also for non-actionable watchlist rows
  actionable: boolean;
  score_label: string;
  signal_ts: string | null;
  expires_at: string | null;
  created_at: string;
  last_seen_at: string;
  provider: string | null;
  lean: string | null;
  wait_reasons: string[];
  thesis: string | null;
  conditions: string[] | null;
  rank: number | null;
  correlated_with_rank: number | null;
}

export interface ScoreComponent {
  name: string;
  weight: number;
  raw: number;
  points: number;
  detail: string;
}
export interface ScorePenalty {
  name: string;
  points: number;
  detail: string;
}
export interface ScoreBreakdown {
  score: number;
  uncapped_score: number;
  label: string;
  calibrated: boolean;
  components: ScoreComponent[];
  penalties: ScorePenalty[];
  cap: { status: ValidationStatus; max_score: number; applied: boolean; reason: string | null };
  method_version: string;
  note: string;
}

export interface ValidationInfo {
  status: ValidationStatus;
  summary: string;
  experiment_id: number | null;
  oos?: { n_trades?: number; expectancy_r?: number | null; win_rate?: number | null; profit_factor?: number | null } | null;
}

export interface SetupTarget {
  label: string;
  price: number;
  rr: number;
  basis: string;
}
export interface SetupDetail {
  direction: "BUY" | "SELL";
  setup_type: string;
  status: string;
  entry_low: number;
  entry_high: number;
  entry_ref: number;
  stop_loss: number;
  invalidation: number;
  targets: SetupTarget[];
  risk_reward: number;
  poi: { kind: string; low: number; high: number; ts: number };
  confirmations: { type: string; kind: string; time: string; evidence: string }[];
  conditions: string[];
  warnings: string[];
  reasoning: { entry: string; stop: string; targets: string[] };
  cost_r: number;
  trigger_ts: number | null;
}

export interface MtfRow {
  timeframe: string;
  status: TfStatus;
  role: string;
  relevant_to_style: boolean;
  reason: string | null;
  n_bars: number;
  derived_from: string | null;
  stale_bars: number | null;
  trend?: number;
  direction?: number;
  summary?: string;
  last_break?: string | null;
  stance?: "supports" | "opposes" | "neutral";
}

export interface AnalogueNeighbor {
  ts: number;
  similarity: number;
  timeframe: string;
  forward_return_atr: Record<string, number>;
  mfe_atr: number;
  mae_atr: number;
  outcome: "tp_first" | "sl_first" | "timeout";
}
interface Freq {
  k: number;
  n: number;
  frequency: number | null;
  ci_low: number | null;
  ci_high: number | null;
}
interface Summ {
  mean: number;
  ci_low: number;
  ci_high: number;
  median: number;
  pct_positive: number;
  n: number;
}
export interface AnalogueEvidence {
  available: boolean;
  reason?: string | null;
  n_obs?: number;
  n_library?: number;
  sample_quality?: "insufficient" | "limited" | "moderate";
  horizon_bars?: number;
  horizons?: number[];
  tp_atr?: number;
  sl_atr?: number;
  tp_first?: Freq;
  sl_first?: Freq;
  base_rate?: Freq;
  edge_vs_base?: number | null;
  edge_within_noise?: boolean;
  forward_return_atr?: Record<string, Summ | null>;
  mfe_atr?: Summ | null;
  mae_atr?: Summ | null;
  neighbors?: AnalogueNeighbor[];
  note?: string;
  kind?: string;
}

export interface OverlayZone {
  kind: string;
  direction: string;
  from: number;
  low: number;
  high: number;
}
export interface OppEvidence {
  actionable: boolean;
  note: string | null;
  scope: string;
  symbol: string;
  provider: string;
  lean: string;
  wait_reasons: string[];
  score: ScoreBreakdown | null;
  score_label: string;
  validation: ValidationInfo;
  analogues: AnalogueEvidence;
  setup: SetupDetail | null;
  multi_timeframe: MtfRow[];
  thesis?: string;
  structure?: {
    timeframe: string;
    summary: string;
    last_break: string | null;
    last_break_bars_ago: number | null;
    zone: string | null;
    range_position: number | null;
    notable_events: { kind: string; direction: string; ts: number; price: number | null; evidence: string }[];
    live_zones: { kind: string; direction: string; low: number; high: number; dist_atr: number | null; evidence: string }[];
    levels: { kind: string; low: number; high: number; evidence: string }[];
  };
  candlesticks?: { kind: string; direction: string; ts: number; time: string; evidence: string; role: string; candle: { o: number; h: number; l: number; c: number } }[];
  risks?: { opposing_evidence: string[]; warnings: string[] };
  chart?: {
    timeframe: string;
    zones: OverlayZone[];
    levels: { kind: string; low: number; high: number; from: number | null; touches: number | null }[];
    trendlines: { kind: string; from_ts: number; from_price: number; to_ts: number; to_price: number }[];
    markers: { kind: string; direction: string; ts: number; price: number | null }[];
    analogue_markers: { ts: number; outcome: string; similarity: number }[];
  };
  data?: { setup_timeframe: string; n_bars: number; stale_bars: number | null; derived_from: string | null; last_bar: string; volume_available: boolean };
}
export interface OpportunityDetail extends Opportunity {
  evidence: OppEvidence;
  status_history: { status: string; at: string; note: Record<string, unknown> | null }[];
  style_profile: { min_rr: number; min_evidence: number; horizon_bars: number; max_cost_r: number; label: string; scope: string };
}

export interface OppTfInfo {
  timeframe: string;
  status: TfStatus;
  n_bars: number;
  last_ts: number | null;
  stale_bars: number | null;
  derived_from: string | null;
  reason: string | null;
  reused: boolean;
}
export interface OppInstrument {
  symbol: string;
  status: "scanned" | "unavailable" | "unsupported" | "failed";
  reason?: string;
  provider?: string;
  provider_status?: string;
  provider_symbol?: string;
  timeframes?: OppTfInfo[];
}
export interface OppStyleBest {
  style: OppStyle;
  label: string;
  scope: string;
  setup_timeframes: string[];
  best: Opportunity | null;
  fallback_wait: Opportunity | null;
}
export interface OppScanInfo {
  id: number;
  status: string;
  trigger: string;
  started_at: string | null;
  finished_at: string | null;
  config_version: string;
  summary: {
    instruments_requested: number;
    instruments_scanned: number;
    instruments_unavailable: string[];
    timeframes_completed: number;
    timeframes_total: number;
    opportunities_actionable: number;
    opportunities_watchlist: number;
    wait: number;
    data_freshness: { max_stale_bars: number | null; median_stale_bars: number | null };
    latest_candle_ts: number | null;
  };
}
export interface OppSummary {
  scan: OppScanInfo | null;
  running_scan: { id: number; status: string; started_at: string | null } | null;
  next_scan: { enabled: boolean; interval_minutes: number; next_run_estimate: string | null; note: string };
  score_label: string;
  styles: OppStyleBest[];
  ranking: Opportunity[];
  instruments: OppInstrument[];
}
export interface ScanAccepted {
  id: number;
  status: string;
  poll_url: string;
  deduplicated: boolean;
}
export interface OppValidationRow {
  symbol: string;
  style: OppStyle;
  timeframe: string;
  status: ValidationStatus;
  summary: string;
  experiment_id: number;
  oos: { n_trades?: number; expectancy_r?: number | null; win_rate?: number | null; profit_factor?: number | null; max_drawdown_r?: number | null };
  oos_gross_zero_cost?: { expectancy_r?: number | null };
}
export interface OppValidation {
  meta: Record<string, unknown>;
  results: OppValidationRow[];
  reference_backtests: { id: number; symbol: string; strategy: string; timeframe: string; metrics: Record<string, number | null>; created_at: string }[];
  note: string;
}

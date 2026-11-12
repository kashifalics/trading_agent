// Paper trading (docs/PAPER_TRADING.md): simulated orders on live candles, no broker.
import type { PlanTarget, ScoreFactor } from "@/lib/signal-types";
import type { TradeManagement } from "@/lib/decision-types";

export type PaperStatus = "pending" | "open" | "closed" | "cancelled" | "missed" | "expired" | "skipped";
export type PaperExitReason = "target" | "stop" | "invalidated" | "tp_before_fill" | "expired" | "chased" | "gapped";

export interface PaperTrade {
  id: number;
  account_id: number | null;
  symbol: string;
  timeframe: string;
  direction: "BUY" | "SELL";
  order_type: "market" | "limit";
  status: PaperStatus;
  exit_reason: PaperExitReason | null;
  note: string | null;
  score: number | null;
  grade: "A" | "B" | null;
  setup_type: string | null;
  entry_type: string | null;
  session: string | null;
  signal_time: string;
  detected_at: string;
  valid_until: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  invalidation: number | null;
  planned_rr: number | null;
  fill_price: number | null;
  filled_at: string | null;
  exit_price: number | null;
  closed_at: string | null;
  risk: number | null;
  spread: number;
  spread_r: number | null;
  r_gross: number | null;
  r_net: number | null;
  mfe_r: number | null;
  mae_r: number | null;
  last_price: number | null;
  last_price_at: string | null;
  unrealized_r: number | null;
  account_taken: boolean;
  account_note: string | null;
  risk_amount: number | null;
  pnl: number | null;
  unrealized_pnl: number | null;
  summary: string | null;
  config_version: string | null;
  /** HOLD / EXIT / WAIT for open or pending trades (backend app/decision). */
  management?: TradeManagement | null;
}

/** The plan exactly as the Signals page showed it when the signal was recorded. */
export interface PaperPlanSnapshot {
  summary?: string;
  score?: number;
  checks_met?: number;
  checks_total?: number;
  factors?: ScoreFactor[];
  targets?: PlanTarget[];
  reasons_for?: string[];
  reasons_against?: string[];
  conditions?: string[];
  warnings?: string[];
  probability_note?: string;
}

export interface PaperTradeDetail extends PaperTrade {
  plan: PaperPlanSnapshot | null;
}

export interface TradeMetrics {
  n_trades: number;
  win_rate?: number;
  profit_factor?: number | null;
  expectancy_r?: number;
  expectancy_r_ci_low?: number | null;
  expectancy_r_ci_high?: number | null;
  max_drawdown_r?: number;
  total_r?: number;
  avg_win_r?: number | null;
  avg_loss_r?: number | null;
}

export interface PaperVerdict {
  status: "collecting" | "no_edge" | "negative" | "validated";
  n: number;
  needed: number;
  summary: string;
  ci95?: [number, number];
  p_value?: number;
}

export interface BreakdownRow {
  key: string;
  n: number;
  win_rate: number;
  expectancy_r: number;
  total_r: number;
  backtest?: { status: string; expectancy_r: number | null; n_trades: number | null } | null;
}

export interface PaperAccount {
  id: number;
  name: string;
  start_balance: number;
  risk_pct: number;
  max_open_positions: number;
  max_daily_loss_pct: number;
  is_active: boolean;
  created_at: string;
  balance: number;
  start_of_day_balance: number;
  today_pnl: number;
  live_trades: number;
  can_trade: boolean;
  blocked_reason: string | null;
  risk_per_trade: number;
  equity: number;
  unrealized_pnl: number;
  open_risk: number;
  return_pct: number | null;
}

export interface PaperAccountSummary extends PaperAccount {
  metrics: TradeMetrics;
  max_drawdown: number;
  equity_curve: { t: string; balance: number; id?: number }[];
  skipped_signals: number;
}

export interface CycleResult {
  symbol: string;
  status: string;
  reason?: string | null;
  sync_note?: string;
  new: { id: number; timeframe: string; side: string; order_type: string }[];
  updated: { id: number; timeframe: string; status: string; exit_reason: string | null }[];
}

export interface PaperWorker {
  enabled: boolean;
  interval_s: number;
  running: boolean;
  cycles: number;
  last_cycle_at: string | null;
  last_duration_s: number | null;
  last_results: CycleResult[] | null;
  last_error: string | null;
}

export type BreakdownKey = "series" | "symbol" | "timeframe" | "setup_type" | "score_band" | "direction" | "order_type" | "session";

export interface PaperSummary {
  generated_at: string;
  account: PaperAccountSummary;
  forward: TradeMetrics & {
    verdict: PaperVerdict;
    counts: Record<PaperStatus, number>;
    signals_recorded: number;
    limit_fill_rate: number | null;
    since: string | null;
    equity_curve: { t: string; r: number; id: number }[];
  };
  backtest: { n_trades: number; expectancy_r: number | null; note: string };
  breakdowns: Record<BreakdownKey, BreakdownRow[]>;
  open: PaperTrade[];
  pending: PaperTrade[];
  recent: PaperTrade[];
  worker: PaperWorker;
  method: string[];
  disclaimer: string;
}

export interface PaperTradesPage {
  items: PaperTrade[];
  total: number;
  limit: number;
  offset: number;
}

export interface PaperRunResult {
  results: CycleResult[];
  duration_s: number;
  finished_at: string;
}

export interface PaperAccountChanges {
  name?: string;
  risk_pct?: number;
  max_open_positions?: number;
  max_daily_loss_pct?: number;
  start_balance?: number;
}

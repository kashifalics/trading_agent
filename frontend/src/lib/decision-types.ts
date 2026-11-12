// The central trading decision, computed by the backend (app/decision). The frontend only displays it: it never re-decides.

export type CallDecision = "ENTER" | "WAIT" | "EXIT" | "NO TRADE";

export interface CallTarget {
  label: string;
  price: number;
  rr: number | null;
}

export interface CallLevels {
  entry: number;
  entry_zone: number[] | null;
  entry_mode: string | null;
  stop_loss: number;
  targets: CallTarget[];
  risk_reward: number | null;
  invalidation: number | null;
}

export interface CallCheck {
  name: string;
  passed: boolean;
  detail: string;
  fix: string | null;
}

export interface TradeManagement {
  trade_id: number;
  status: "open" | "pending";
  direction: "BUY" | "SELL";
  action: "HOLD" | "EXIT" | "WAIT" | "NO TRADE";
  reason: string;
  exit_kind?: string;
  entry_price: number | null;
  current_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  stop_distance: number | null;
  target_distance: number | null;
  unrealized_r: number | null;
  unrealized_pnl: number | null;
}

export interface TradeCall {
  decision: CallDecision;
  /** e.g. "WAIT — UNVALIDATED SETUP", "NO TRADE — CONDITION FAILED" */
  label: string;
  headline: string;
  symbol?: string;
  timeframe: string | null;
  direction: "BUY" | "SELL" | "NONE";
  setup: string | null;
  entry_mode: "immediate" | "conditional" | null;
  /** Entry, stop and targets: present only with ENTER. */
  levels: CallLevels | null;
  /** Experimental mode only: the technical levels of an unvalidated setup, clearly marked. */
  hypothetical: (CallLevels & { label: string; note: string; direction: string }) | null;
  watch?: { zone: number[] | null; invalidation: number | null } | null;
  technical_status?: string;
  technical_detail?: string | null;
  data_quality: { status: string; detail: string | null };
  /** research_status: the underlying research verdict (validated, untested, no_edge, negative) */
  validation: { status: "validated" | "not_validated"; label: string; note: string; research_status?: string };
  alignment?: {
    higher: { timeframe: string; label: string | null; agrees: boolean | null }[];
    confirmation: { timeframe: string | null; status: string };
    summary: string;
  } | null;
  checks?: CallCheck[];
  failed_checks?: CallCheck[];
  reasons_for?: string[];
  reasons_against?: string[];
  next_condition: string | null;
  invalidation?: string | null;
  wait_kind?: string | null;
  score?: number | null;
  score_note?: string;
  experimental?: boolean;
  trade?: TradeManagement | null;
  /** the price the decision was checked against, and where it came from (live quote or last close) */
  price_now?: number | null;
  price_source?: string | null;
  exit_price?: number | null;
  exit_reason?: string | null;
}

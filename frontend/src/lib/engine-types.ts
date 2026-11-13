// Types for /api/v1/engine (backend: app/strategy_engine, docs/engine_v2/DESIGN.md).
import type { TradeManagement } from "@/lib/decision-types";

export type EngineAction = "BUY" | "SELL" | "WAIT FOR BUY" | "WAIT FOR SELL" | "EXIT" | "NO TRADE";
export type EntryStatus = "READY" | "WAITING FOR ENTRY" | "ENTRY MISSED" | "EXPIRED" | "INVALIDATED";
export type RegimeLabel = "TRENDING" | "RANGING" | "CONSOLIDATING" | "HIGH_VOLATILITY" | "UNKNOWN";

export interface EngineRegime {
  label: RegimeLabel;
  name: string;
  direction: number;
  subtype: string | null;
  reason: string;
  metrics: Record<string, number | null>;
  criteria: { name: string; met: boolean; value: number | null }[];
  criteria_met: number;
}

export interface EngineTarget {
  label: string;
  price: number;
  rr: number;
  rr_net: number;
  basis: string;
}

export interface EnginePlan {
  entry_mode: "market" | "limit" | "stop";
  entry: number;
  entry_zone: number[] | null;
  stop_loss: number;
  risk: number;
  risk_atr: number;
  targets: EngineTarget[];
  risk_reward: number;
  spread: number;
  cost_r: number;
  invalidation: number;
  invalidation_text: string;
  entry_status: EntryStatus;
  trigger: string;
  signal_time: string;
  expires_at: string;
  price_now: number;
}

export interface EngineCandidate {
  strategy: string;
  name: string;
  side: "BUY" | "SELL";
  direction: number;
  status: "ready" | "pending" | "forming" | "rejected" | "not run";
  reasons: string[];
  missing: string[];
  plan: EnginePlan | null;
}

export interface EngineTimeframe {
  timeframe: string;
  group: string;
  context_tf: string | null;
  regime: EngineRegime;
  context_regime: EngineRegime | null;
  action: Exclude<EngineAction, "EXIT">;
  direction: "BUY" | "SELL" | null;
  strategy: string | null;
  strategy_name: string | null;
  technical_status: "QUALIFIED" | "DEVELOPING" | "INVALIDATED" | "NO SETUP";
  research_status: string | null;
  plan_label: string | null;
  plan: EnginePlan | null;
  why: string[];
  missing: string[];
  next_action: string;
  headline: string;
  agreeing: string[];
  conflict: { buy: string; sell: string; resolution: string } | null;
  candidates: EngineCandidate[];
  n_bars: number;
  data_time: string | null;
}

export interface EnginePrimary {
  action: EngineAction;
  kind: "opportunity" | "exit" | "no_trade" | "no_data";
  headline: string;
  timeframe?: string;
  why?: string[];
  exit?: TradeManagement & { trade_id: number; timeframe: string };
}

export interface EngineRisk {
  eligible: boolean;
  blocks: string[];
  size: { risk_amount: number; units: number; lots: number; contract_size: number } | null;
}

export interface EngineTradeRow {
  id: number;
  timeframe: string;
  direction: "BUY" | "SELL";
  status: string;
  fill_price: number | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  last_price: number | null;
  unrealized_r: number | null;
  management?: TradeManagement;
}

export interface EngineItem {
  symbol: string;
  name?: string;
  status: "ok" | "unavailable" | "failed";
  reason?: string;
  price_precision?: number;
  price_now?: number | null;
  price_source?: string;
  data_time?: string | null;
  generated_at?: string;
  market_open?: boolean;
  session?: { label: string; entry_allowed: boolean; block_reason: string | null };
  primary: EnginePrimary;
  opportunity: Omit<EngineTimeframe, "candidates"> | null;
  exits?: (TradeManagement & { trade_id: number; timeframe: string })[];
  risk?: EngineRisk | null;
  tfs: { timeframe: string; action: EngineTimeframe["action"]; strategy_name: string | null; regime: RegimeLabel; regime_name: string;
    entry_status: EntryStatus | null; risk_reward: number | null; headline: string }[];
  trades: EngineTradeRow[];
}

export interface EngineSummary {
  items: EngineItem[];
  generated_at: string;
  engine_version: string;
  research_note: string;
  news: { available: boolean; note: string };
}

export interface EngineDetail extends Omit<EngineItem, "tfs" | "trades"> {
  timeframes: EngineTimeframe[];
  trades: (EngineTradeRow & { management?: TradeManagement })[];
  research: { status: Record<string, string>; note: string; names: Record<string, string> };
  news: { available: boolean; note: string };
}

export interface SignalRecord {
  id: number;
  symbol: string;
  timeframe: string;
  strategy: string;
  strategy_name: string | null;
  direction: "BUY" | "SELL";
  regime: string | null;
  entry_mode: string;
  entry: number;
  stop_loss: number;
  tp1: number;
  tp2: number | null;
  tp3: number | null;
  status: string;
  research_status: string;
  signal_time: string;
  detected_at: string;
  closed_at: string | null;
  best_target: number;
  last_price: number | null;
  history: { status: string; at: string; price: number | null; note: string }[];
  hypothetical: true;
}

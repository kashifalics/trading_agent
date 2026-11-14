import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ActiveTradesPage from "@/app/(terminal)/active/page";
import { NAV } from "@/components/layout/app-shell";
import { mockApi, renderWithClient } from "@/test/utils";

// TEST DATA ONLY: illustrative prices, never real trades.
const NOW = new Date().toISOString();

const paper = (id: number, over: Record<string, unknown>) => ({
  id, account_id: 1, symbol: "XAUUSD", timeframe: "1H", direction: "BUY", order_type: "market", status: "open", exit_reason: null, note: null,
  score: null, grade: null, setup_type: null, entry_type: null, session: null, signal_time: NOW, detected_at: NOW, valid_until: NOW,
  entry_price: 3900, stop_loss: 3890, take_profit: 3930, invalidation: null, planned_rr: 3, fill_price: 3900, filled_at: NOW, exit_price: null,
  closed_at: null, risk: 10, spread: 0.3, spread_r: 0.03, r_gross: null, r_net: null, mfe_r: null, mae_r: null, last_price: 3912,
  last_price_at: NOW, unrealized_r: 1.2, account_taken: true, account_note: null, risk_amount: 50, pnl: null, unrealized_pnl: 60, summary: null,
  config_version: "v1", management: { trade_id: id, status: "open", direction: "BUY", action: "HOLD", reason: "between the stop and the target",
    entry_price: 3900, current_price: 3912, stop_loss: 3890, take_profit: 3930, stop_distance: 22, target_distance: 18, unrealized_r: 1.2,
    unrealized_pnl: 60 }, ...over,
});

const PAPER = {
  items: [
    paper(1, {}),
    paper(2, { symbol: "EURUSD", direction: "SELL", entry_price: 1.1, fill_price: 1.1, stop_loss: 1.101, take_profit: 1.097, last_price: 1.1005,
      unrealized_r: -0.5, unrealized_pnl: -25, management: { trade_id: 2, status: "open", direction: "SELL", action: "EXIT",
        reason: "price is at the stop-loss", entry_price: 1.1, current_price: 1.1005, stop_loss: 1.101, take_profit: 1.097, stop_distance: 0,
        target_distance: 0.0035, unrealized_r: -0.5, unrealized_pnl: -25 } }),
    paper(3, { status: "pending", fill_price: null, filled_at: null, unrealized_r: null, management: null }),  // an order, not a trade
  ],
  total: 3, limit: 200, offset: 0,
};

const signal = (id: number, over: Record<string, unknown>) => ({
  id, symbol: "XAUUSD", timeframe: "15m", strategy: "breakout_retest", strategy_name: "Breakout and retest", direction: "BUY", regime: "RANGING",
  entry_mode: "market", entry: 100, stop_loss: 99, tp1: 102, tp2: 103, tp3: 105, status: "ACTIVE", research_status: "NOT VALIDATED",
  signal_time: NOW, detected_at: NOW, triggered_at: NOW, closed_at: null, best_target: 0, last_price: 101.5, history: [], hypothetical: true,
  ...over,
});

const SIGNALS = {
  items: [
    signal(11, {}),  // BUY 100 -> 101.5 with 1.0 risk: +1.5R
    signal(12, { symbol: "EURUSD", direction: "SELL", entry: 50, stop_loss: 51, tp1: 48.5, tp2: 47, tp3: 45, status: "TP1 HIT", best_target: 1,
      last_price: 48 }),  // SELL 50 -> 48 with 1.0 risk: +2.0R
    signal(13, { status: "WAITING FOR ENTRY", triggered_at: null, last_price: 100.4 }),  // not in the market yet
    signal(14, { status: "STOP LOSS HIT", closed_at: NOW, last_price: 99 }),  // closed
  ],
  open_statuses: ["WAITING FOR ENTRY", "ENTRY READY", "ACTIVE", "TP1 HIT", "TP2 HIT"],
};

const INSTRUMENTS = [
  { id: 1, canonical_symbol: "XAUUSD", name: "Gold", asset_class: "metal", quote_currency: "USD", price_precision: 2, tick_size: 0.01,
    calendar: "fx_weekly", session_tz: "America/New_York" },
  { id: 2, canonical_symbol: "EURUSD", name: "Euro", asset_class: "fx", quote_currency: "USD", price_precision: 5, tick_size: 0.00001,
    calendar: "fx_weekly", session_tz: "America/New_York" },
];

function routes(paperBody: unknown = PAPER, signalBody: unknown = SIGNALS) {
  return mockApi({
    "GET /api/v1/paper/trades": paperBody,
    "GET /api/v1/engine/signals": signalBody,
    "GET /api/v1/market/instruments": INSTRUMENTS,
  });
}

describe("Active Trades page", () => {
  it("lists open paper trades and in-market engine signals in two labelled sections", async () => {
    routes();
    renderWithClient(<ActiveTradesPage />);
    const paperSec = await screen.findByTestId("active-paper");
    expect(within(paperSec).getByText(/simulated paper account/i)).toBeInTheDocument();
    expect(await within(paperSec).findByTestId("paper-1")).toHaveTextContent("XAUUSD");
    expect(within(paperSec).getByTestId("paper-1")).toHaveTextContent("HOLD");
    expect(within(paperSec).getByTestId("paper-2")).toHaveTextContent("EXIT");
    expect(within(paperSec).getByTestId("paper-2")).toHaveTextContent("1.10000");  // EURUSD at its own precision
    expect(within(paperSec).queryByTestId("paper-3")).toBeNull();  // a pending order is not an active trade
    const sigSec = screen.getByTestId("active-signals");
    expect(within(sigSec).getByText(/hypothetical/i)).toBeInTheDocument();
    expect(await within(sigSec).findByTestId("sig-11")).toHaveTextContent("ACTIVE");
    expect(within(sigSec).getByTestId("sig-12")).toHaveTextContent("TP1 HIT");
    expect(within(sigSec).queryByTestId("sig-13")).toBeNull();  // waiting for entry: not in the market
    expect(within(sigSec).queryByTestId("sig-14")).toBeNull();  // closed
  });

  it("computes R now for BUY and SELL signals from the last price, entry and risk", async () => {
    routes();
    renderWithClient(<ActiveTradesPage />);
    expect(await screen.findByTestId("sig-11")).toHaveTextContent("+1.5R");
    expect(screen.getByTestId("sig-12")).toHaveTextContent("+2.0R");
    expect(await screen.findByTestId("paper-2")).toHaveTextContent("-0.5R");
  });

  it("sums the open trades in a summary strip", async () => {
    routes();
    renderWithClient(<ActiveTradesPage />);
    await screen.findByTestId("paper-1");  // data loaded (the tiles show "…" until then)
    await screen.findByTestId("sig-11");
    const kp = screen.getByTestId("kpi-active-paper");
    expect(kp).toHaveTextContent("2");
    expect(kp).toHaveTextContent("+0.7R");
    const ks = screen.getByTestId("kpi-active-signals");
    expect(ks).toHaveTextContent("2");
    expect(ks).toHaveTextContent("1 active · 1 past TP1 · 0 past TP2");
  });

  it("says so when nothing is active", async () => {
    routes({ items: [], total: 0, limit: 200, offset: 0 }, { items: [], open_statuses: [] });
    renderWithClient(<ActiveTradesPage />);
    expect(await screen.findByText("No open paper trades")).toBeInTheDocument();
    expect(await screen.findByText("No engine signal in the market")).toBeInTheDocument();
  });

  it("is in the sidebar right after Paper Trading", () => {
    const i = NAV.findIndex((n) => n.href === "/paper");
    expect(NAV[i + 1]).toMatchObject({ label: "Active Trades", href: "/active" });
  });
});

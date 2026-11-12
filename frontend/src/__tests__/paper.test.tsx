import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import PaperTradingPage from "@/app/(terminal)/paper/page";
import { EquityCurve } from "@/components/domain/paper";
import type { PaperSummary, PaperTrade, PaperTradeDetail } from "@/lib/paper-types";
import { mockApi, renderWithClient } from "@/test/utils";

const base: PaperTrade = {
  id: 1, account_id: 1, symbol: "XAUUSD", timeframe: "15m", direction: "BUY", order_type: "market", status: "closed", exit_reason: "target",
  note: "TP1 reached", score: 72, grade: "A", setup_type: "trend_pullback", entry_type: "market", session: "London",
  signal_time: "2026-11-02T10:00:00Z", detected_at: "2026-11-02T10:00:20Z", valid_until: "2026-11-02T14:00:00Z", entry_price: 2000,
  stop_loss: 1995, take_profit: 2010, invalidation: 1995, planned_rr: 2, fill_price: 2000.5, filled_at: "2026-11-02T10:01:00Z", exit_price: 2010,
  closed_at: "2026-11-02T10:04:00Z", risk: 5.5, spread: 0.3, spread_r: 0.0545, r_gross: 1.727, r_net: 1.673, mfe_r: 1.727, mae_r: -0.1,
  last_price: 2010, last_price_at: "2026-11-02T10:05:00Z", unrealized_r: null, account_taken: true, account_note: null, risk_amount: 50,
  pnl: 83.64, unrealized_pnl: null, summary: "BUY 15m trend pullback at bullish order block: 72/100", config_version: "2026-11-07.1",
};
const open: PaperTrade = { ...base, id: 2, symbol: "BTCUSDT", timeframe: "1H", status: "open", exit_reason: null, note: null, exit_price: null, closed_at: null,
  r_gross: null, r_net: null, pnl: null, fill_price: 67000, stop_loss: 66500, take_profit: 68000, last_price: 67250, unrealized_r: 0.496, unrealized_pnl: 24.8 };
const pending: PaperTrade = { ...base, id: 3, symbol: "US30", timeframe: "4H", direction: "SELL", order_type: "limit", status: "pending", exit_reason: null,
  note: null, fill_price: null, filled_at: null, exit_price: null, closed_at: null, r_gross: null, r_net: null, pnl: null, account_taken: false,
  account_note: "max open positions (1) reached", risk_amount: null, entry_price: 44100, stop_loss: 44300, take_profit: 43700 };

const SUMMARY: PaperSummary = {
  generated_at: "2026-11-07T12:00:00Z",
  account: {
    id: 1, name: "Paper account", start_balance: 10000, risk_pct: 0.5, max_open_positions: 5, max_daily_loss_pct: 2, is_active: true,
    created_at: "2026-11-01T00:00:00Z", balance: 10083.64, start_of_day_balance: 10083.64, today_pnl: 0, live_trades: 1, can_trade: true,
    blocked_reason: null, risk_per_trade: 50.42, equity: 10108.44, unrealized_pnl: 24.8, open_risk: 50, return_pct: 0.84,
    metrics: { n_trades: 1, win_rate: 1, expectancy_r: 1.673, total_r: 1.673 }, max_drawdown: 0, equity_curve: [], skipped_signals: 1,
  },
  forward: {
    n_trades: 1, win_rate: 1, expectancy_r: 1.673, expectancy_r_ci_low: null, expectancy_r_ci_high: null, total_r: 1.673, profit_factor: null, max_drawdown_r: 0,
    verdict: { status: "collecting", n: 1, needed: 100, summary: "1 of 100 closed trades: too few to tell an edge from luck, no conclusion yet" },
    counts: { pending: 1, open: 1, closed: 1, cancelled: 0, missed: 0, expired: 0, skipped: 0 }, signals_recorded: 3, limit_fill_rate: null,
    since: "2026-11-02T10:00:20Z", equity_curve: [{ t: "2026-11-02T10:04:00Z", r: 1.673, id: 1 }],
  },
  backtest: { n_trades: 400, expectancy_r: -0.048, note: "historical replay" },
  breakdowns: {
    series: [{ key: "XAUUSD 15m", n: 1, win_rate: 1, expectancy_r: 1.673, total_r: 1.673, backtest: { status: "no_edge", expectancy_r: -0.35, n_trades: 60 } }],
    symbol: [], timeframe: [{ key: "15m", n: 1, win_rate: 1, expectancy_r: 1.673, total_r: 1.673 }], setup_type: [], score_band: [], direction: [], order_type: [], session: [],
  },
  open: [open], pending: [pending], recent: [base],
  worker: { enabled: true, interval_s: 60, running: false, cycles: 12, last_cycle_at: "2026-11-07T11:59:30Z", last_duration_s: 3.2, last_results: [], last_error: null },
  method: ["Every technically complete setup is recorded when the backend first sees it (immediate entry -> market order, limit plan -> limit order), whatever the customer decision: this is the forward test of the unvalidated rules; nothing is backfilled."],
  disclaimer: "Paper trading: simulated orders on live candles, no broker and no real money.",
};

const DETAIL: PaperTradeDetail = {
  ...base,
  plan: {
    summary: base.summary ?? undefined, reasons_for: ["Higher-timeframe alignment: 4H and 1D bullish"], reasons_against: ["News filter unavailable"],
    factors: [{ key: "htf_alignment", label: "Higher-timeframe alignment", max: 20, points: 20, checks: [
      { key: "htf_4H", label: "4H trend bullish", max: 10, points: 10, met: true, detail: "4H is strong bullish" }] }],
  },
};

const routes = (over: Record<string, unknown> = {}) => ({
  "GET /api/v1/paper/summary": SUMMARY,
  "GET /api/v1/paper/trades": { items: [base], total: 1, limit: 200, offset: 0 },
  "GET /api/v1/paper/trades/1": DETAIL,
  ...over,
});

afterEach(() => vi.unstubAllGlobals());

describe("Paper Trading page", () => {
  it("shows the verdict, forward test, account, open positions and pending orders", async () => {
    mockApi(routes());
    renderWithClient(<PaperTradingPage />);
    expect(await screen.findByText("Collecting evidence")).toBeInTheDocument();
    expect(screen.getByText("1 / 100 closed trades")).toBeInTheDocument();
    expect(screen.getByText(/-0.05R/)).toBeInTheDocument(); // backtest reference beside the live record
    const stats = screen.getByTestId("forward-stats");
    expect(within(stats).getByText("3")).toBeInTheDocument();
    expect(within(stats).getAllByText("+1.67R", { selector: "span" })).toHaveLength(2); // expectancy and total (one trade)
    expect(within(screen.getByTestId("account-stats")).getByText("$10,083.64")).toBeInTheDocument();
    expect(screen.getByTestId("account-gate")).toHaveTextContent("1 of 5 trade slots in use");
    expect(screen.getByText("Open positions (1)")).toBeInTheDocument();
    expect(screen.getByText("+0.50R")).toBeInTheDocument();
    expect(screen.getByText("Pending orders (1)")).toBeInTheDocument();
    expect(screen.getByText("Limit 44,100.00")).toBeInTheDocument();
    expect(screen.getByText("skipped")).toHaveAttribute("title", "max open positions (1) reached");
    expect(screen.getByTestId("worker-line")).toHaveTextContent("Automatic cycle every 60s");
    expect(screen.getByText("The curve starts after the second closed trade")).toBeInTheDocument();
  });

  it("lists closed trades and expands one into the plan as it was when the signal fired", async () => {
    mockApi(routes());
    renderWithClient(<PaperTradingPage />);
    const result = await screen.findByText("TP1 hit");
    await userEvent.click(result);
    const detail = await screen.findByTestId("paper-trade-detail");
    expect(within(detail).getByText(/Filled 2,000.50/)).toBeInTheDocument();
    expect(within(detail).getByText("Higher-timeframe alignment: 4H and 1D bullish")).toBeInTheDocument();
    expect(within(detail).getByTestId("checklist")).toHaveTextContent("4H trend bullish");
    expect(within(detail).getByText(/Taken by the account, risking \$50.00/)).toBeInTheDocument();
  });

  it("runs a cycle on demand and reports what it did", async () => {
    const api = mockApi(routes({ "POST /api/v1/paper/run": { duration_s: 2.5, finished_at: "x", results: [
      { symbol: "XAUUSD", status: "ok", new: [{ id: 9, timeframe: "5m", side: "BUY", order_type: "market" }], updated: [] },
      { symbol: "US30", status: "failed", reason: "boom", new: [], updated: [] }] } }));
    renderWithClient(<PaperTradingPage />);
    await userEvent.click(await screen.findByRole("button", { name: /run cycle now/i }));
    expect(await screen.findByText("Cycle finished in 2.5s: 1 new signal, 0 trade updates; failed: US30.")).toBeInTheDocument();
    expect(api.calls.some((c) => c.key === "POST /api/v1/paper/run")).toBe(true);
  });

  it("validates and saves the account rules, and resets only after confirmation", async () => {
    const api = mockApi(routes({ "PATCH /api/v1/paper/account": SUMMARY.account, "POST /api/v1/paper/account/reset": SUMMARY.account }));
    renderWithClient(<PaperTradingPage />);
    const risk = await screen.findByLabelText("Risk per trade %");
    await userEvent.clear(risk);
    await userEvent.type(risk, "9");
    expect(screen.getByRole("button", { name: "Save rules" })).toBeDisabled();
    await userEvent.clear(risk);
    await userEvent.type(risk, "1");
    await userEvent.click(screen.getByRole("button", { name: "Save rules" }));
    await waitFor(() => expect(api.calls.find((c) => c.key === "PATCH /api/v1/paper/account")?.body).toEqual(
      { risk_pct: 1, max_open_positions: 5, max_daily_loss_pct: 2 }));
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    await userEvent.click(screen.getByRole("button", { name: "Reset account" }));
    expect(confirm).toHaveBeenCalled();
    expect(api.calls.some((c) => c.key === "POST /api/v1/paper/account/reset")).toBe(false);
  });

  it("warns when automatic paper trading is off", async () => {
    mockApi(routes({ "GET /api/v1/paper/summary": { ...SUMMARY, worker: { ...SUMMARY.worker, enabled: false } } }));
    renderWithClient(<PaperTradingPage />);
    expect(await screen.findByText(/Automatic paper trading is off/)).toBeInTheDocument();
  });
});

describe("EquityCurve", () => {
  it("draws the curve and reads out a trade on keyboard focus", () => {
    render(<EquityCurve label="Cumulative R" points={[{ t: "2026-11-02T10:04:00Z", v: 1.6 }, { t: "2026-11-03T09:00:00Z", v: 0.5 }]} />);
    const svg = screen.getByRole("img", { name: "Cumulative R: 2 closed trades, now +0.50R" });
    fireEvent.keyDown(svg, { key: "ArrowRight" });
    expect(screen.getByRole("status")).toHaveTextContent("Trade 1 · 2026-11-02 10:04Z");
    expect(screen.getByRole("status")).toHaveTextContent("Cumulative R: +1.60R (this trade +1.60R)");
  });
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import TradeHistoryPage from "@/app/(terminal)/history/page";
import { NAV } from "@/components/layout/app-shell";
import { mockApi, renderWithClient } from "@/test/utils";

// TEST DATA ONLY: 120 closed paper trades. Trade n closes n hours after the start (n = 120 is the newest close), but was DETECTED in
// the opposite order, so sorting by detection would be wrong. Every third trade wins +2R, the others lose -1R; every fourth was taken by
// the account (risk 50 USD), the rest were tracked but not taken.
const T0 = Date.UTC(2026, 10, 1, 0, 0);
const iso = (ms: number) => new Date(ms).toISOString();

function trade(n: number, over: Record<string, unknown> = {}) {
  const win = n % 3 === 0;
  const taken = n % 4 === 0;
  const r = win ? 2 : -1;
  const closed = T0 + n * 3600_000;
  return {
    id: n, account_id: 1, symbol: n % 2 ? "XAUUSD" : "EURUSD", timeframe: "1H", direction: n % 5 ? "BUY" : "SELL", order_type: "market",
    status: "closed", exit_reason: win ? "target" : "stop", note: null, score: null, grade: null, setup_type: null, entry_type: null,
    session: null, signal_time: iso(T0), detected_at: iso(T0 + (200 - n) * 60_000), valid_until: iso(closed), entry_price: 100, stop_loss: 99,
    take_profit: 102, invalidation: null, planned_rr: 2, fill_price: 100, filled_at: iso(closed - 90 * 60_000), exit_price: win ? 102 : 99,
    closed_at: iso(closed), risk: 1, spread: 0.02, spread_r: 0.02, r_gross: r, r_net: r, mfe_r: null, mae_r: null, last_price: null,
    last_price_at: null, unrealized_r: null, account_taken: taken, account_note: null, risk_amount: taken ? 50 : null,
    pnl: taken ? r * 50 : null, unrealized_pnl: null, summary: null, config_version: "v1", management: null, ...over,
  };
}

const ITEMS = [
  ...Array.from({ length: 120 }, (_, k) => trade(k + 1)),
  trade(200, { status: "cancelled", exit_reason: "invalidated", fill_price: null, filled_at: null, r_net: null, pnl: null }),  // never filled
  trade(201, { status: "missed", exit_reason: "tp_before_fill", fill_price: null, filled_at: null, r_net: null, pnl: null }),
];

const INSTRUMENTS = [
  { id: 1, canonical_symbol: "XAUUSD", name: "Gold", asset_class: "metal", quote_currency: "USD", price_precision: 2, tick_size: 0.01,
    calendar: "fx_weekly", session_tz: "America/New_York" },
  { id: 2, canonical_symbol: "EURUSD", name: "Euro", asset_class: "fx", quote_currency: "USD", price_precision: 5, tick_size: 0.00001,
    calendar: "fx_weekly", session_tz: "America/New_York" },
];

function routes(items: unknown[] = ITEMS, total = 120) {
  return mockApi({
    "GET /api/v1/paper/trades": { items, total, limit: 200, offset: 0 },
    "GET /api/v1/market/instruments": INSTRUMENTS,
  });
}

const rows = () => screen.getAllByTestId(/^hist-\d+$/);

describe("Trade History page", () => {
  it("lists the last 100 closed trades by default, newest close first, never unfilled orders", async () => {
    routes();
    renderWithClient(<TradeHistoryPage />);
    await screen.findByTestId("hist-120");
    const r = rows();
    expect(r).toHaveLength(100);
    expect(r[0]).toHaveAttribute("data-testid", "hist-120");
    expect(r[99]).toHaveAttribute("data-testid", "hist-21");
    expect(screen.queryByTestId("hist-200")).toBeNull();  // cancelled: never a trade
    expect(screen.queryByTestId("hist-201")).toBeNull();  // missed
    expect(screen.getByTestId("history-total")).toHaveTextContent("120 closed in total");
  });

  it("switches between the last 50, 100 and 200 trades", async () => {
    routes();
    const user = userEvent.setup();
    renderWithClient(<TradeHistoryPage />);
    await screen.findByTestId("hist-120");
    await user.click(screen.getByRole("tab", { name: "Last 50" }));
    expect(rows()).toHaveLength(50);
    await user.click(screen.getByRole("tab", { name: "Last 200" }));
    expect(rows()).toHaveLength(120);  // every closed trade there is
  });

  it("shows the result, R, dollars only for trades the account took, and the time held", async () => {
    routes();
    renderWithClient(<TradeHistoryPage />);
    const won = await screen.findByTestId("hist-120");  // win, taken
    expect(won).toHaveTextContent("TARGET");
    expect(won).toHaveTextContent("+2.00R");
    expect(within(won).getByTestId("pnl-120")).toHaveTextContent("+$100.00");
    expect(won).toHaveTextContent("1h 30m");
    expect(won).toHaveTextContent("100.00000");  // EURUSD at its own precision (5 decimals)
    const lost = screen.getByTestId("hist-119");  // loss, not taken
    expect(lost).toHaveTextContent("STOP");
    expect(lost).toHaveTextContent("-1.00R");
    expect(within(lost).getByTestId("pnl-119")).toHaveTextContent("—");
    expect(within(lost).getByTestId("pnl-119")).toHaveAttribute("title", expect.stringContaining("not taken by the account"));
  });

  it("sums the trades shown and runs the cumulative R from the oldest one", async () => {
    routes();
    renderWithClient(<TradeHistoryPage />);
    await screen.findByTestId("hist-120");
    // trades 21..120: 34 wins (+2R), 66 losses (-1R) = +2R; taken trades 24, 28, .., 120: 9 wins (+100) and 16 losses (-50) = +100 USD
    const s = screen.getByTestId("history-summary");
    expect(s).toHaveTextContent("100 trades");
    expect(s).toHaveTextContent("34 wins · 66 losses (34%)");
    expect(s).toHaveTextContent("+2.0R");
    expect(s).toHaveTextContent("+0.02R per trade");
    expect(s).toHaveTextContent("+$100.00 on 25 account trades");
    expect(s).toHaveTextContent("best +2.00R · worst -1.00R");
    expect(screen.getByTestId("cum-21")).toHaveTextContent("+2.0R");  // the oldest shown trade starts the running total
    expect(screen.getByTestId("cum-22")).toHaveTextContent("+1.0R");
    expect(screen.getByTestId("cum-120")).toHaveTextContent("+2.0R");
  });

  it("says so when nothing has closed yet", async () => {
    routes([], 0);
    renderWithClient(<TradeHistoryPage />);
    expect(await screen.findByText("No closed paper trades yet")).toBeInTheDocument();
  });

  it("is in the sidebar right after Active Trades", () => {
    const i = NAV.findIndex((n) => n.href === "/active");
    expect(NAV[i + 1]).toMatchObject({ label: "Trade History", href: "/history" });
  });
});

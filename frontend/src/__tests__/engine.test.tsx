import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import SignalsPage from "@/app/(terminal)/signals/page";
import { useSettings } from "@/lib/store";
import { ENGINE_SUMMARY, GOLD_BUY, RECORD, regime } from "@/test/engine";
import { mockApi, renderWithClient } from "@/test/utils";

const DETAIL = {
  ...GOLD_BUY, research: { status: {}, note: "Not tested yet.", names: {} }, news: { available: false, note: "News is NOT filtered." }, trades: [],
  timeframes: [
    { ...GOLD_BUY.opportunity, candidates: [
      { strategy: "trend_pullback", name: "Trend-following pullback", side: "BUY", direction: 1, status: "ready", reasons: ["momentum recovered"], missing: [], plan: null },
      { strategy: "sweep_reversal", name: "Liquidity-sweep reversal", side: "SELL", direction: -1, status: "forming", reasons: [],
        missing: ["market-structure shift: a close below 3,901.00 (a sweep alone is not a trade)"], plan: null },
      { strategy: "range_reversion", name: "Range mean reversion", side: "BUY", direction: 1, status: "not run", reasons: [], missing: [], plan: null }] },
    { timeframe: "4H", group: "swing", context_tf: "1D", regime: regime("HIGH_VOLATILITY", "High volatility / abnormal"), context_regime: null, action: "NO TRADE",
      direction: null, strategy: null, strategy_name: null, technical_status: "NO SETUP", research_status: null, plan_label: null, plan: null, why: [],
      missing: ["Volatility back to normal"], next_action: "Wait", headline: "NO TRADE: abnormal volatility", agreeing: [], conflict: null, candidates: [], n_bars: 208, data_time: null },
  ],
};

function routes() {
  return mockApi({
    "GET /api/v1/engine": ENGINE_SUMMARY,
    "GET /api/v1/engine/signals": { items: [RECORD], open_statuses: [] },
    "GET /api/v1/engine/XAUUSD": DETAIL,
  });
}

beforeEach(() => useSettings.setState({ experimentalMode: true }));

describe("Signals page (strategy engine)", () => {
  it("shows the action and the exact entry, stop-loss and three targets at once, best first, always labelled unvalidated", async () => {
    routes();
    renderWithClient(<SignalsPage />);
    const gold = await screen.findByTestId("signal-XAUUSD");
    expect(within(gold).getByTestId("primary-action")).toHaveTextContent(/^BUY$/);
    expect(within(gold).getByTestId("setup-line")).toHaveTextContent("Trend-following pullback · 1H · Trending up");
    expect(within(gold).getByTestId("lv-entry")).toHaveTextContent("3,915.29");
    expect(within(gold).getByTestId("lv-sl")).toHaveTextContent("3,906.83");
    expect(within(gold).getByTestId("lv-tp1")).toHaveTextContent("3,942.40");
    expect(within(gold).getByTestId("lv-tp2")).toHaveTextContent("3,961.80");
    expect(within(gold).getByTestId("lv-tp3")).toHaveTextContent("3,981.00");
    expect(within(gold).getByTestId("plan-facts")).toHaveTextContent("Risk/reward 1:3.20 (TP1)");
    expect(within(gold).getByTestId("plan-facts")).toHaveTextContent("status READY");
    expect(within(gold).getByTestId("plan-label")).toHaveTextContent("UNVALIDATED — HYPOTHETICAL TRADE PLAN");
    expect(within(gold).getByTestId("research-status")).toHaveTextContent("INSUFFICIENT EVIDENCE");
    expect(within(gold).getByTestId("why")).toHaveTextContent("pullback to EMA20");
    expect(within(gold).getByTestId("invalidation")).toHaveTextContent("a 1H close below 3,907.60");
    expect(within(gold).getByTestId("next-action")).toHaveTextContent("BUY now near 3,915.29");
    const order = within(screen.getByTestId("signal-cards")).getAllByTestId(/^signal-[A-Z0-9]+$/).map((e) => e.getAttribute("data-testid"));
    expect(order).toEqual(["signal-US30", "signal-XAUUSD", "signal-EURUSD", "signal-GBPUSD"]); // the backend's ranking is kept
    expect(screen.getByTestId("signals-note")).toHaveTextContent("No strategy has passed research validation yet");
  });

  it("says WAIT FOR SELL with the exact entry condition, and NO TRADE with the reasons", async () => {
    routes();
    renderWithClient(<SignalsPage />);
    const eur = await screen.findByTestId("signal-EURUSD");
    expect(within(eur).getByTestId("primary-action")).toHaveTextContent("WAIT FOR SELL");
    expect(within(eur).getByTestId("lv-entry")).toHaveTextContent("1.11012");
    expect(within(eur).getByTestId("lv-entry")).toHaveTextContent("zone 1.10994–1.11012");
    expect(within(eur).getByTestId("next-action")).toHaveTextContent("SELL limit at 1.11012 on a retest");
    expect(within(eur).getByTestId("plan-facts")).toHaveTextContent("WAITING FOR ENTRY");
    const gbp = screen.getByTestId("signal-GBPUSD");
    expect(within(gbp).getByTestId("primary-action")).toHaveTextContent("NO TRADE");
    expect(within(gbp).getByTestId("no-trade")).toHaveTextContent("only 101 complete candles");
    expect(within(gbp).queryByTestId("lv-entry")).toBeNull(); // no prices without a qualified plan
  });

  it("shows a paper-trade EXIT separately and keeps the new opportunity visible", async () => {
    routes();
    renderWithClient(<SignalsPage />);
    const us30 = await screen.findByTestId("signal-US30");
    expect(within(us30).getByTestId("exit-banner")).toHaveTextContent("EXIT the tracked paper BUY trade (3m)");
    expect(within(us30).getByTestId("exit-banner")).toHaveTextContent("at or beyond the stop-loss");
    expect(within(us30).getByTestId("primary-action")).toHaveTextContent("WAIT FOR BUY"); // the opportunity, not hidden by the trade
    expect(within(us30).getByTestId("paper-trades")).toHaveTextContent("separate from the signal above");
    expect(within(us30).getByTestId("paper-trades")).toHaveTextContent("-1.2R");
  });

  it("hides unvalidated prices when hypothetical plans are switched off", async () => {
    useSettings.setState({ experimentalMode: false });
    routes();
    renderWithClient(<SignalsPage />);
    const gold = await screen.findByTestId("signal-XAUUSD");
    expect(within(gold).getByTestId("plan-hidden")).toBeInTheDocument();
    expect(within(gold).queryByTestId("lv-entry")).toBeNull();
    expect(gold).not.toHaveTextContent("3,915.29");
    expect(within(gold).getByTestId("primary-action")).toHaveTextContent(/^BUY$/); // the action itself is still shown
    await userEvent.click(screen.getByLabelText("Show hypothetical trade plans (unvalidated)"));
    expect(await within(gold).findByTestId("lv-entry")).toHaveTextContent("3,915.29");
  });

  it("opens every timeframe and every strategy's verdict, and lists the signal lifecycle", async () => {
    routes();
    const user = userEvent.setup();
    renderWithClient(<SignalsPage />);
    const gold = await screen.findByTestId("signal-XAUUSD");
    await user.click(within(gold).getByTestId("toggle-detail"));
    const tf = await within(gold).findByTestId("etf-1H");
    expect(within(gold).getByTestId("etf-4H")).toHaveTextContent("High volatility / abnormal");
    await user.click(tf);
    const list = await within(gold).findByTestId("strategies-1H");
    expect(list).toHaveTextContent("Liquidity-sweep reversal SELL");
    expect(list).toHaveTextContent("a sweep alone is not a trade");
    expect(list).toHaveTextContent("Not run in a trending up regime: Range mean reversion");
    const hist = await screen.findByTestId("rec-11");
    expect(hist).toHaveTextContent("TP1 HIT");
    expect(hist).toHaveTextContent("3,942.40 / 3,961.80 / 3,981.00");
  });
});

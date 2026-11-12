import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SignalsPage from "@/app/(terminal)/signals/page";
import { DEFAULT_CONTRACT_SIZE, positionSize } from "@/lib/position-size";
import type { SignalAnalysis, SignalsSummary, TimeframePlan } from "@/lib/signal-types";
import { useSettings } from "@/lib/store";
import { CALL_EMPTY, CALL_ENTER, CALL_READY, CALL_READY_X, CALL_WATCH } from "@/test/calls";
import { CANDLES } from "@/test/fixtures";
import { mockApi, renderWithClient } from "@/test/utils";

vi.mock("@/components/charts/candle-chart", () => ({
  CandleChart: (p: { candles: unknown[]; lines?: { title: string }[] }) => (
    <div data-testid="candle-chart">{p.candles.length} candles; lines: {(p.lines ?? []).map((l) => l.title).join(",")}</div>
  ),
}));

const TFS = ["1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M", "3M", "6M", "12M"];
const NOTE = "Win probability: not yet statistically validated";

const empty = (timeframe: string, over: Partial<TimeframePlan> = {}): TimeframePlan => ({
  timeframe, group: "intraday", group_label: "Intraday", bias_tfs: ["4H", "1D"], confirm_tf: "15m", status: "insufficient_data", state: "NO_SETUP",
  instruction: "NO TRADE", decision: "NO TRADE", direction: null, score: null, grade: null, buy_score: null, sell_score: null, targets: [], factors: [],
  reasons_for: [], reasons_against: ["fewer than 120 complete candles"], conditions: [], warnings: [], blocked: [], market: null, probability_note: NOTE,
  win_probability: null, call: { ...CALL_EMPTY, timeframe }, ...over,
});

const factors = [
  { key: "htf_alignment", label: "Higher-timeframe alignment", max: 20, points: 20, checks: [
    { key: "htf_4H", label: "4H trend bullish", max: 10, points: 10, met: true, detail: "4H is strong bullish (HH/HL)" },
    { key: "htf_1D", label: "1D trend bullish", max: 10, points: 10, met: true, detail: "1D is bullish" }] },
  { key: "liquidity", label: "Liquidity event", max: 15, points: 0, checks: [
    { key: "liquidity_sweep", label: "Liquidity sweep", max: 15, points: 0, met: false, detail: "no sell-side liquidity sweep in the recent window" }] },
];

const READY = empty("1H", {
  status: "ok", state: "ENTRY_READY", instruction: "EXECUTE NOW", decision: "BUY", direction: "BUY", side: "BUY", score: 72, grade: "A", buy_score: 72,
  sell_score: 30, setup_type: "trend_pullback", entry_type: "market", entry: 3950.5, entry_zone: [3940, 3952], zone_kind: "order_block", stop_loss: 3935.25,
  invalidation: 3940, targets: [{ label: "TP1", price: 3990, rr: 2.59, basis: "swing_high" }, { label: "TP2", price: 4012, rr: 4.03, basis: "previous_day_high" }],
  risk_reward: 2.59, risk_atr: 1.4, cost_r: 0.02, factors, checks_met: 9, checks_total: 13,
  reasons_for: ["4H trend bullish: 4H is strong bullish (HH/HL)"], reasons_against: ["Liquidity sweep missing: no sell-side liquidity sweep in the recent window"],
  conditions: ["Enter BUY near 3,950.5; skip it if price is already above 3,955 (never chase)"], summary: "BUY 1H trend pullback at order block: 72/100",
  signal_time: "2026-11-06T10:00:00+00:00", valid_until: "2026-11-07T02:00:00+00:00",
  market: { timeframe: "1H", class: "strong_bullish", label: "Strong bullish", direction: 1, structure: "HH/HL", observation: "price is inside a bullish order block", last_event: null, zone: "discount", range_position: 0.3, last_close: 3950.5, atr: 11 },
  track_record: { available: true, status: "no_edge", summary: "only 40 out-of-sample trades", win_probability: null, oos: { n_trades: 40, tp1_hit_rate: 0.4, expectancy_r: 0.05, profit_factor: 1.1, expectancy_r_ci_low: -0.3, expectancy_r_ci_high: 0.4 } },
  call: CALL_READY,
});
const WATCH = empty("4H", {
  status: "ok", state: "WATCHLIST", group: "swing", group_label: "Swing", bias_tfs: ["1D", "1W"], confirm_tf: "1H", decision: "WAIT", side: "SELL",
  score: 66, buy_score: 20, sell_score: 66, setup_type: "bos_retest", entry_type: "limit", entry: 3990, stop_loss: 4030, invalidation: 4020,
  targets: [{ label: "TP1", price: 3900, rr: 2.25, basis: "support_band" }], risk_reward: 2.25, factors,
  blocked: ["structural stop is 4.6 ATR from entry (maximum 4.0 ATR for swing)"], reasons_against: ["Blocked: structural stop is 4.6 ATR from entry (maximum 4.0 ATR for swing)"],
  call: CALL_WATCH,
});

const analysis = (over: Partial<SignalAnalysis> = {}): SignalAnalysis => ({
  symbol: "XAUUSD", name: "Gold Spot", status: "ok", provider: "biquote", provider_status: "active", price_precision: 2, generated_at: new Date().toISOString(),
  config_version: "2026-11-07.1", market_open: true, quote: { price: 3951, bid: 3950.85, ask: 3951.15, spread: 0.3, time: new Date().toISOString(), delayed: false, provider: "biquote" },
  spread_model: 0.3, overall: { label: "Bullish", score: 0.6, direction: 1, detail: "1W bullish, 1D bullish", groups: { "Short-term": "Mixed", Intraday: "Bullish", Swing: "Bullish", "Long-term": "Bullish" } },
  timeframes: TFS.map((t) => (t === "1H" ? { timeframe: t, status: "completed", n_bars: 500, label: "Strong bullish", structure: "HH/HL", direction: 1, last_close: 3950.5 } : { timeframe: t, status: "insufficient_data", n_bars: 0, reason: "not enough stored candles" })),
  plans: TFS.map((t) => (t === "1H" ? READY : t === "4H" ? WATCH : empty(t))), active: ["1H"], watchlist: ["4H"], best: READY,
  counts: { entry_ready: 1, waiting: 0, developing: 0, watchlist: 1, no_setup: 12 }, session: "London",
  news_filter: { available: false, note: "No economic-calendar integration." }, report: { final_instruction: "EXECUTE NOW", text: "x" }, disclaimer: "Analysis only.", call: CALL_READY, ...over,
});

const SUMMARY: SignalsSummary = {
  generated_at: new Date().toISOString(), config_version: "2026-11-07.1", disclaimer: "Analysis only.",
  items: [
    { symbol: "XAUUSD", status: "ok", provider: "biquote", price_precision: 2, overall: analysis().overall, best: { timeframe: "1H", state: "ENTRY_READY", instruction: "EXECUTE NOW", decision: "BUY", direction: "BUY", score: 72, grade: "A", entry: 3950.5, stop_loss: 3935.25, tp1: 3990, risk_reward: 2.59 }, call: CALL_READY },
    { symbol: "BTCUSDT", status: "unavailable", reason: "no stored candles yet: press Sync to load data from the provider", provider: "binance", call: { ...CALL_EMPTY, timeframe: null } },
  ],
};

function routes(extra: Record<string, unknown> = {}) {
  return mockApi({
    "GET /api/v1/signals": SUMMARY,
    "GET /api/v1/signals/XAUUSD": analysis(),
    "POST /api/v1/signals/XAUUSD/sync": { synced: true, provider: "biquote", fetched: ["1m"], notes: [], analysis: analysis() },
    "GET /api/v1/signals/BTCUSDT": analysis({ symbol: "BTCUSDT", status: "unavailable", reason: "no stored candles yet", provider: "binance", plans: [], timeframes: [], best: null, overall: null, counts: null }),
    "POST /api/v1/signals/BTCUSDT/sync": { synced: true, provider: "binance", notes: ["1M: data sync failed"], analysis: analysis({ symbol: "BTCUSDT", status: "unavailable", reason: "no stored candles yet", provider: "binance", plans: [], timeframes: [], best: null, overall: null }) },
    "GET /api/v1/market/candles": { ...CANDLES, symbol: "XAUUSD", provider: "biquote" },
    ...extra,
  });
}

beforeEach(() => useSettings.setState({ liveSignals: true, experimentalMode: false, accountBalance: 1000, riskPct: 0.5, contractSizes: {} }));

/** The same analysis with the 1H plan's call (and the headline call) swapped: what the backend returns in another mode. */
const withCall = (c: typeof CALL_READY, over: Partial<SignalAnalysis> = {}) =>
  analysis({ call: c, plans: TFS.map((t) => (t === "1H" ? { ...READY, call: c } : t === "4H" ? WATCH : empty(t))), ...over });
const isExp = (u?: URL) => u?.searchParams.get("experimental") === "true";
afterEach(() => vi.unstubAllGlobals());

describe("position size", () => {
  it("sizes the position from the actual stop distance and the contract size", () => {
    const r = positionSize(1000, 0.5, 3950.5, 3948.0, 100)!;
    expect(r.riskAmount).toBeCloseTo(5);
    expect(r.stopDistance).toBeCloseTo(2.5);
    expect(r.units).toBeCloseTo(2);
    expect(r.lots).toBeCloseTo(0.02);
    expect(positionSize(1000, 0.5, 100, 100, 100)).toBeNull();
  });

  it("sizes an FX trade in standard lots: $10,000 at 1% with a 20-pip stop is 0.5 lots", () => {
    const r = positionSize(10_000, 1, 1.1226, 1.1206, DEFAULT_CONTRACT_SIZE.EURUSD)!;
    expect(r.riskAmount).toBeCloseTo(100);
    expect(r.stopDistance).toBeCloseTo(0.002, 6);
    expect(r.lots).toBeCloseTo(0.5, 6);
    expect(positionSize(10_000, 0, 1.1226, 1.1206, 100_000)).toBeNull(); // no risk budget, no size
  });
});

describe("Signals page", () => {
  it("leads with the backend decision: a technically complete but unvalidated setup is WAIT, never EXECUTE NOW, and its levels stay hidden", async () => {
    routes();
    renderWithClient(<SignalsPage />);
    const card = (await screen.findAllByTestId("call-card"))[0];
    expect(within(card).getByText("Decision now")).toBeInTheDocument();
    expect(within(card).getByTestId("call-decision")).toHaveTextContent("WAIT — UNVALIDATED SETUP");
    expect(card).toHaveTextContent("XAUUSD · BUY · 1H · trend pullback");
    expect(within(card).getByTestId("call-validation")).toHaveTextContent("Not validated");
    expect(within(card).getByTestId("call-next")).toHaveTextContent("at least 100 out-of-sample trades");
    expect(within(card).getByTestId("call-data")).toHaveTextContent("ok");
    expect(within(card).queryByTestId("call-hypothetical")).toBeNull();
    expect(screen.getByTestId("overall-bias")).toHaveTextContent("Bullish");
    // the old execution words and the technical levels never reach the customer for an unvalidated setup
    expect(screen.queryByText(/EXECUTE NOW|PLACE LIMIT ORDER/)).toBeNull();
    expect(document.body).not.toHaveTextContent("3,935.25");
    expect(document.body).not.toHaveTextContent("3,990.00");
    expect(screen.getByTestId("levels-hidden")).toBeInTheDocument();
    expect(await screen.findByTestId("candle-chart")).toHaveTextContent("lines:");
    expect(screen.getByTestId("candle-chart")).not.toHaveTextContent("SL");
    expect(screen.getByText(/Every instrument and timeframe gets one decision/)).toHaveTextContent("WAIT — UNVALIDATED SETUP");
  });

  it("experimental mode asks the backend for hypothetical levels and shows them clearly marked, without changing the decision", async () => {
    useSettings.setState({ experimentalMode: true });
    const api = routes({
      "GET /api/v1/signals/XAUUSD": (_i?: RequestInit, u?: URL) => (isExp(u) ? withCall(CALL_READY_X) : analysis()),
      "POST /api/v1/signals/XAUUSD/sync": (_i?: RequestInit, u?: URL) => ({ synced: true, provider: "biquote", notes: [], analysis: isExp(u) ? withCall(CALL_READY_X) : analysis() }),
    });
    renderWithClient(<SignalsPage />);
    const hypo = (await screen.findAllByTestId("call-hypothetical"))[0];
    expect(hypo).toHaveTextContent("HYPOTHETICAL — UNVALIDATED · BUY");
    expect(hypo).toHaveTextContent("3,935.25");
    expect(hypo).toHaveTextContent("1:2.59");
    expect(screen.getAllByTestId("call-decision")[0]).toHaveTextContent("WAIT — UNVALIDATED SETUP");
    expect(screen.queryByText(/EXECUTE NOW/)).toBeNull();
    expect(await screen.findByTestId("candle-chart")).toHaveTextContent("Hypothetical Entry BUY,SL,TP1,TP2");
    expect(api.fn.mock.calls.some(([u]) => String(u).includes("experimental=true"))).toBe(true);
  });

  it("shows ENTER with entry, stop, targets and position size only when the backend says ENTER", async () => {
    routes({ "GET /api/v1/signals/XAUUSD": withCall(CALL_ENTER), "POST /api/v1/signals/XAUUSD/sync": { synced: true, provider: "biquote", notes: [], analysis: withCall(CALL_ENTER) } });
    renderWithClient(<SignalsPage />);
    const card = (await screen.findAllByTestId("call-card"))[0];
    expect(within(card).getByTestId("call-decision")).toHaveTextContent(/^ENTER$/);
    expect(within(card).getByTestId("call-validation")).toHaveTextContent("Validated");
    expect(card).toHaveTextContent("3,935.25");
    expect(card).toHaveTextContent("TP1 3,990.00 (2.59R)");
    expect(card).toHaveTextContent("1:2.59");
    expect(card).toHaveTextContent("no order is placed");
    const detail = screen.getByTestId("plan-detail");
    expect(within(detail).getByTestId("size-result")).toHaveTextContent("lots");
    expect(await within(detail).findByTestId("candle-chart")).toHaveTextContent("lines: Entry BUY,SL,TP1,TP2");
    expect(screen.queryByText(/EXECUTE NOW/)).toBeNull();
  });

  it("lists every timeframe with its decision and opens the checklist of the selected one", async () => {
    routes();
    const user = userEvent.setup();
    renderWithClient(<SignalsPage />);
    const table = await screen.findByTestId("tf-table");
    expect(within(table).getAllByRole("row")).toHaveLength(15); // header + 14 timeframes
    expect(within(table).getByTestId("tf-row-1H")).toHaveTextContent("WAIT — UNVALIDATED SETUP");
    expect(within(table).getByTestId("tf-row-4H")).toHaveTextContent("NO TRADE — CONDITION FAILED");
    expect(within(table).getByTestId("tf-row-5m")).toHaveTextContent("NO TRADE — DATA");
    const detail = screen.getByTestId("plan-detail");
    expect(within(detail).getByTestId("checklist")).toHaveTextContent("4H trend bullish");
    expect(within(detail).getByTestId("reasons-against")).toHaveTextContent("Liquidity sweep missing");
    await user.click(within(table).getByTestId("tf-row-4H"));
    await waitFor(() => expect(screen.getByTestId("plan-detail")).toHaveTextContent("structural stop is 4.6 ATR"));
    expect(screen.getByTestId("plan-detail")).toHaveTextContent("NO TRADE — CONDITION FAILED");
    expect(screen.getByTestId("plan-detail")).toHaveTextContent("Watchlist"); // the technical state, shown below the decision
  });

  it("syncs fresh candles on load and on demand", async () => {
    const api = routes();
    const user = userEvent.setup();
    renderWithClient(<SignalsPage />);
    await waitFor(() => expect(api.calls.some((c) => c.key === "POST /api/v1/signals/XAUUSD/sync")).toBe(true));
    const before = api.calls.filter((c) => c.key === "POST /api/v1/signals/XAUUSD/sync").length;
    await user.click(await screen.findByTestId("refresh-now"));
    await waitFor(() => expect(api.calls.filter((c) => c.key === "POST /api/v1/signals/XAUUSD/sync").length).toBeGreaterThan(before));
  });

  it("is honest about instruments without data", async () => {
    routes();
    useSettings.setState({ liveSignals: false });
    const user = userEvent.setup();
    renderWithClient(<SignalsPage />);
    const tab = await screen.findByTestId("tab-BTCUSDT");
    expect(tab).toHaveTextContent("NO TRADE — DATA");
    expect(tab).toHaveTextContent("no data");
    await user.click(tab);
    expect(await screen.findByText("BTCUSDT: no analysis yet")).toBeInTheDocument();
  });

  it("says NO TRADE with the failed condition when nothing qualifies", async () => {
    const none = analysis({ best: null, active: [], call: CALL_WATCH, plans: TFS.map((t) => (t === "4H" ? WATCH : empty(t))) });
    routes({ "GET /api/v1/signals/XAUUSD": none, "POST /api/v1/signals/XAUUSD/sync": { synced: true, provider: "biquote", notes: [], analysis: none } });
    renderWithClient(<SignalsPage />);
    const card = (await screen.findAllByTestId("call-card"))[0];
    expect(within(card).getByTestId("call-decision")).toHaveTextContent("NO TRADE — CONDITION FAILED");
    expect(card).toHaveTextContent("structural stop is 4.6 ATR from entry");
    expect(within(card).getByTestId("call-next")).toHaveTextContent("A setup whose structural stop is within the allowed distance");
    expect(screen.queryByText(/EXECUTE NOW/)).toBeNull();
  });
});

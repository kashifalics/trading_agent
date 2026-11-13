import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSettings } from "@/lib/store";
import { CALL_PRED_BUY_X, CALL_PRED_SELL } from "@/test/calls";
import { ENGINE_SUMMARY } from "@/test/engine";
import { CANDLES, INSTRUMENTS, QUOTES, analysis } from "@/test/fixtures";
import { mockApi, renderWithClient } from "@/test/utils";
import ChartPage from "@/app/(terminal)/chart/page";
import DashboardPage from "@/app/(terminal)/page";
import PredictionsPage from "@/app/(terminal)/predictions/page";

vi.mock("@/components/charts/candle-chart", () => ({
  CandleChart: (p: { candles: unknown[]; lines?: { title: string }[] }) => (
    <div data-testid="candle-chart">{p.candles.length} candles; lines: {(p.lines ?? []).map((l) => l.title).join(",")}</div>
  ),
}));

const base = {
  "GET /api/v1/market/instruments": INSTRUMENTS,
  "GET /api/v1/market/quotes": QUOTES,
  "GET /api/v1/market/coverage": [],
  "GET /api/v1/models": { items: [], total: 0, limit: 50, offset: 0 },
  "GET /api/v1/analysis": { items: [], total: 0, limit: 5, offset: 0 },
  "GET /api/v1/predictions": { items: [], total: 0, limit: 25, offset: 0 },
  "GET /api/v1/patterns": { symbol: "BTCUSDT", timeframe: "1H", provider: "binance", n_bars: 0, events: [], swings: [], message: "Not enough stored candles; sync data first." },
  "GET /api/v1/health": { status: "ok", version: "0.1.0", env: "test", time: "", mode: "analysis_only", components: {} },
  "GET /api/v1/market/timeframes": [],
};

beforeEach(() => useSettings.setState({ symbol: "BTCUSDT", timeframe: "1H", experimentalMode: false }));
afterEach(() => vi.unstubAllGlobals());

describe("Dashboard", () => {
  it("shows real quote states and never fabricates data for unsupported instruments", async () => {
    mockApi(base);
    renderWithClient(<DashboardPage />);
    const btc = await screen.findByTestId("quote-BTCUSDT");
    await waitFor(() => expect(within(btc).getByText("77,488.75")).toBeInTheDocument());
    const us30 = screen.getByTestId("quote-US30");
    expect(within(us30).getByText("No data source configured")).toBeInTheDocument();
    expect(within(us30).queryByText(/\d{2},\d{3}/)).not.toBeInTheDocument();
    expect(within(screen.getByTestId("quote-XAUUSD")).getByText("API key required")).toBeInTheDocument();
    expect(await screen.findByText("No predictions yet")).toBeInTheDocument();
    expect(screen.getByText(/No models trained/)).toBeInTheDocument();
  });

  it("shows the same action per instrument as the Signals page, with prices and what comes next", async () => {
    useSettings.setState({ experimentalMode: true });
    mockApi({ ...base, "GET /api/v1/engine": ENGINE_SUMMARY });
    renderWithClient(<DashboardPage />);
    const card = await screen.findByTestId("decisions-now");
    const gold = (await within(card).findByText("XAUUSD")).closest("tr")!;
    expect(gold).toHaveTextContent("BUY");
    expect(gold).toHaveTextContent("1H · Trend-following pullback");
    expect(within(card).getByTestId("levels-XAUUSD")).toHaveTextContent("3,915.29 · 3,906.83 · 3,942.40");
    expect(within(card).getByText("US30").closest("tr")!).toHaveTextContent("EXIT");
    expect(within(card).getByText("GBPUSD").closest("tr")!).toHaveTextContent("NO TRADE");
    expect(card).not.toHaveTextContent(/EXECUTE NOW/);
  });

  it("hides unvalidated prices on the Overview when hypothetical plans are off", async () => {
    useSettings.setState({ experimentalMode: false });
    mockApi({ ...base, "GET /api/v1/engine": ENGINE_SUMMARY });
    renderWithClient(<DashboardPage />);
    const card = await screen.findByTestId("decisions-now");
    expect(await within(card).findByTestId("levels-XAUUSD")).toHaveTextContent("hidden (unvalidated)");
    useSettings.setState({ experimentalMode: true });
  });

  it("labels a last-known price as delayed, never as live", async () => {
    const delayed = QUOTES.map((q) => q.symbol === "BTCUSDT"
      ? { ...q, delayed: true, message: "Last known price (2026-11-06 21:59Z): market closed or quote stale, not a live price" } : q);
    mockApi({ ...base, "GET /api/v1/market/quotes": delayed });
    renderWithClient(<DashboardPage />);
    const btc = await screen.findByTestId("quote-BTCUSDT");
    await waitFor(() => expect(within(btc).getByText("delayed")).toBeInTheDocument());
    expect(within(btc).queryByText("live")).not.toBeInTheDocument();
    expect(within(btc).getByText(/not a live price/)).toBeInTheDocument();
  });

  it("asks for the platform API key when the server answers 401", async () => {
    mockApi({ ...base, "GET /api/v1/market/instruments": { error: { code: "unauthorized", message: "API key required" } } },
      { "GET /api/v1/market/instruments": 401 });
    renderWithClient(<DashboardPage />);
    expect((await screen.findAllByText("API key required")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /enter it in settings/i })[0]).toHaveAttribute("href", "/settings");
  });

  it("surfaces a backend outage with a retry action instead of blank cards", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("offline"); }));
    renderWithClient(<DashboardPage />);
    expect((await screen.findAllByText("Backend unreachable")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /retry/i }).length).toBeGreaterThan(0);
  });
});

describe("Chart analysis workflow", () => {
  it("runs an analysis job, polls to completion and shows the backend decision; unvalidated levels stay hidden", async () => {
    let polls = 0;
    const { calls } = mockApi({
      ...base,
      "GET /api/v1/market/candles": CANDLES,
      "POST /api/v1/analysis/run": { id: 7, status: "queued", poll_url: "/api/v1/analysis/7" },
      "GET /api/v1/analysis/7": () => analysis("BUY", ++polls < 2 ? "running" : "completed"),
    });
    renderWithClient(<ChartPage />);
    expect(await screen.findByText("No analysis yet")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("candle-chart")).toHaveTextContent("3 candles"));
    await userEvent.click(screen.getByRole("button", { name: /run analysis/i }));
    const panel = screen.getByTestId("decision-panel");
    await waitFor(() => expect(within(panel).getByTestId("call-decision")).toHaveTextContent("WAIT — UNVALIDATED SETUP"), { timeout: 6000 });
    expect(within(panel).getByTestId("call-validation")).toHaveTextContent("Not validated");
    expect(panel).not.toHaveTextContent("101.00"); // the technical stop is withheld without ENTER
    expect(within(panel).queryByTestId("hypothetical-plan")).toBeNull();
    expect(screen.getByTestId("candle-chart")).not.toHaveTextContent("BUY entry");
    expect(screen.queryByText(/EXECUTE NOW/)).toBeNull();
    const run = calls.find((c) => c.key === "POST /api/v1/analysis/run");
    expect(run?.body).toMatchObject({ symbol: "BTCUSDT", timeframe: "1H", lookback_bars: 1500, auto_sync: true });
  }, 15000);

  it("shows NO TRADE with reasons and no trade levels", async () => {
    mockApi({
      ...base,
      "GET /api/v1/market/candles": CANDLES,
      "GET /api/v1/predictions": { items: [{ id: 9, analysis_id: 7, symbol: "BTCUSDT", timeframe: "1H", decision: "WAIT", created_at: "2026-10-31T20:00:00Z", as_of_ts: "2026-10-31T20:00:00Z" }], total: 1, limit: 10, offset: 0 },
      "GET /api/v1/analysis/7": analysis("WAIT"),
    });
    renderWithClient(<ChartPage />);
    const panel = await screen.findByTestId("decision-panel");
    await waitFor(() => expect(within(panel).getByTestId("call-decision")).toHaveTextContent(/^NO TRADE$/));
    expect(within(panel).getByTestId("call-headline")).toHaveTextContent(/below the \+\/-0.35 threshold/);
    expect(within(panel).queryByText(/stop loss/i)).not.toBeInTheDocument();
  });

  it("experimental mode shows the hypothetical plan, clearly marked, without changing the decision", async () => {
    useSettings.setState({ experimentalMode: true });
    const api = mockApi({
      ...base,
      "GET /api/v1/market/candles": CANDLES,
      "GET /api/v1/predictions": { items: [{ id: 9, analysis_id: 7, symbol: "BTCUSDT", timeframe: "1H", decision: "BUY", created_at: "2026-10-31T20:00:00Z", as_of_ts: "2026-10-31T20:00:00Z" }], total: 1, limit: 10, offset: 0 },
      "GET /api/v1/analysis/7": (_i?: RequestInit, u?: URL) => analysis("BUY", "completed", u?.searchParams.get("experimental") === "true" ? CALL_PRED_BUY_X : undefined),
    });
    renderWithClient(<ChartPage />);
    const panel = await screen.findByTestId("decision-panel");
    const plan = await within(panel).findByTestId("hypothetical-plan");
    expect(plan).toHaveTextContent("HYPOTHETICAL — UNVALIDATED plan");
    expect(plan).toHaveTextContent("101.00");
    expect(within(panel).getByTestId("call-hypothetical")).toHaveTextContent("HYPOTHETICAL — UNVALIDATED · BUY");
    expect(within(panel).getByTestId("call-decision")).toHaveTextContent("WAIT — UNVALIDATED SETUP");
    await waitFor(() => expect(screen.getByTestId("candle-chart")).toHaveTextContent("BUY entry,SL,TP1,TP2"));
    expect(api.fn.mock.calls.some(([u]) => String(u).includes("experimental=true"))).toBe(true);
  });

  it("blocks analysis for an instrument with no data source", async () => {
    useSettings.setState({ symbol: "US30" });
    mockApi({ ...base });
    renderWithClient(<ChartPage />);
    expect(await screen.findByText(/has no configured data source/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run analysis/i })).toBeDisabled();
  });

  it("validates the lookback before calling the API", async () => {
    const { calls } = mockApi({ ...base, "GET /api/v1/market/candles": CANDLES });
    renderWithClient(<ChartPage />);
    const input = await screen.findByLabelText("Lookback bars");
    await userEvent.clear(input);
    await userEvent.type(input, "50");
    await userEvent.click(screen.getByRole("button", { name: /run analysis/i }));
    expect(await screen.findByText("Minimum 200 bars")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/v1/analysis/run")).toBe(false);
  });
});

describe("Predictions list", () => {
  it("renders stored predictions and filters server-side", async () => {
    const { calls } = mockApi({
      ...base,
      "GET /api/v1/predictions": {
        items: [{ id: 1, analysis_id: 1, symbol: "BTCUSDT", timeframe: "1H", decision: "SELL", entry_low: 100, entry_high: 101, stop_loss: 103, take_profit: [95], risk_reward: 2.5, data_quality_score: 0.9, outcome: "open", as_of_ts: "2026-10-31T20:00:00Z", call: CALL_PRED_SELL }],
        total: 1, limit: 20, offset: 0,
      },
    });
    renderWithClient(<PredictionsPage />);
    expect(await screen.findByText("WAIT — UNVALIDATED SETUP")).toBeInTheDocument(); // the stored SELL is not validated: never shown as a trade
    const row = screen.getByText("WAIT — UNVALIDATED SETUP").closest("tr")!;
    expect(row).not.toHaveTextContent("103.00");
    expect(row).not.toHaveTextContent("95.00");
    await userEvent.selectOptions(screen.getByLabelText("Filter decision"), "BUY");
    await waitFor(() => expect(calls.some((c) => c.key === "GET /api/v1/predictions")).toBe(true));
  });
});

describe("All-timeframes panel", () => {
  it("shows each pattern's measured track record and never invents one", async () => {
    const frame = (tf: string, trend: number, firing: object[]) => ({ timeframe: tf, bars: 700, status: "ok", structure_trend: trend, last_break: "BOS:bullish", zone: "discount", range_position: 0.3, atr: 5, last_close: 100, live_zones: 2, patterns_firing: firing });
    mockApi({
      ...base,
      "GET /api/v1/patterns/scan": {
        symbol: "BTCUSDT", provider: "binance", recent_bars: 3, evidence_meta: {}, note: "Nothing here is a probability of profit.",
        alignment: { bullish_timeframes: 1, bearish_timeframes: 1, analysed: 2 },
        timeframes: [
          frame("1H", 1, [{ pattern: "fvg_retest", side: "long", bars_ago: 0, verdict: "no_edge_found", evidence: { i_n: 90, i_lift: 0.1, o_n: 40, o_win: 0.3, o_gross: 0.0, o_net: -0.4, o_lift: 0.0, o_holm: 0.9 } }]),
          frame("4H", -1, [{ pattern: "hammer", side: "long", bars_ago: 1, verdict: "no_study_data", evidence: null }]),
          { timeframe: "1M", bars: 40, status: "insufficient_data" },
        ],
      },
    });
    const { default: PatternsPage } = await import("@/app/(terminal)/patterns/page");
    renderWithClient(<PatternsPage />);
    expect(await screen.findByText("1 bullish")).toBeInTheDocument();
    expect(screen.getByText("1 bearish")).toBeInTheDocument();
    expect(screen.getAllByText("no edge").length).toBeGreaterThan(0);
    expect(screen.getAllByText("no track record").length).toBeGreaterThan(0);
    expect(screen.getByText("insufficient stored data")).toBeInTheDocument();
    expect(screen.getByText(/Nothing here is a probability of profit/)).toBeInTheDocument();
  });
});

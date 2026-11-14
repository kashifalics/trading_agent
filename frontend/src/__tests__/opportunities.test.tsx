import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OpportunitiesPage from "@/app/(terminal)/opportunities/page";
import { NAV } from "@/components/layout/app-shell";
import type { Opportunity, OppSummary, OppTfInfo, OpportunityDetail } from "@/lib/opportunity-types";
import { useSettings } from "@/lib/store";
import { CALL_OPP_BUY, CALL_OPP_BUY_X, CALL_OPP_LONG, CALL_OPP_SELL, CALL_OPP_SELL_ENTER, CALL_OPP_WAIT, CALL_OPP_WATCH } from "@/test/calls";
import { CANDLES, INSTRUMENTS } from "@/test/fixtures";
import { mockApi, renderWithClient } from "@/test/utils";

vi.mock("@/components/charts/candle-chart", () => ({
  CandleChart: (p: { candles: unknown[]; lines?: { title: string }[]; zones?: unknown[] }) => (
    <div data-testid="candle-chart">{p.candles.length} candles; lines: {(p.lines ?? []).map((l) => l.title).join(",")}; zones: {(p.zones ?? []).length}</div>
  ),
}));

const NOW = new Date().toISOString();
const opp = (o: Partial<Opportunity>): Opportunity => ({
  id: 1, symbol: "BTCUSDT", style: "swing", is_headline: true, scan_id: 5, last_scan_id: 5, direction: "WAIT", status: "none", setup_timeframe: null, setup_type: null,
  risk_reward: null, evidence_score: null, validation_status: "untested", expected_holding_seconds: null, entry_low: null, entry_high: null, stop_loss: null,
  take_profit_1: null, take_profit_2: null, take_profit_3: null, invalidation: null, side: null, actionable: false, score_label: "Evidence Score — Not Win Probability",
  signal_ts: NOW, expires_at: NOW, created_at: NOW, last_seen_at: NOW, provider: "binance", lean: "undetermined", wait_reasons: [], thesis: null, conditions: null,
  rank: null, correlated_with_rank: null, ...o,
});
const BUY = opp({ id: 11, symbol: "XAUUSD", style: "swing", direction: "BUY", status: "waiting_for_confirmation", setup_timeframe: "4H", setup_type: "trend_pullback", side: "BUY",
  actionable: true, entry_low: 3900.5, entry_high: 3920.25, stop_loss: 3880.1, take_profit_1: 3990, take_profit_2: 4040, take_profit_3: 4100, invalidation: 3885,
  risk_reward: 2.4, evidence_score: 61, expected_holding_seconds: 345600, rank: 1, provider: "twelve_data", thesis: "4H structure is bullish.", call: CALL_OPP_BUY });
const SELL = opp({ id: 12, symbol: "BTCUSDT", style: "intraday", direction: "SELL", status: "entry_triggered", setup_timeframe: "30m", side: "SELL", actionable: true,
  entry_low: 77000, entry_high: 77100, stop_loss: 77400, take_profit_1: 76400, take_profit_2: 76000, take_profit_3: null, invalidation: 77300, risk_reward: 2.0,
  evidence_score: 57, rank: 2, correlated_with_rank: null, call: CALL_OPP_SELL });
const WATCH = opp({ id: 13, symbol: "XAUUSD", style: "intraday", direction: "WAIT", status: "watchlist", side: "BUY", setup_timeframe: "15m", entry_low: 3910, entry_high: 3915,
  stop_loss: 3895, take_profit_1: 3950, take_profit_2: 3970, risk_reward: 1.9, evidence_score: 41, rank: 3, wait_reasons: ["evidence score 41 is below the 55 needed to publish"], call: CALL_OPP_WATCH });
const WAIT = opp({ id: 14, symbol: "BTCUSDT", style: "scalping", direction: "WAIT", status: "none", setup_timeframe: "1m",
  wait_reasons: ["1m: latest candle is 90 bars old; too stale to scalp", "5m: round-trip costs would consume 2.20R"], call: CALL_OPP_WAIT });
const LONG = opp({ id: 15, symbol: "BTCUSDT", style: "long_term", direction: "WAIT", status: "none", wait_reasons: ["1D: BUY: no zone"], call: CALL_OPP_LONG });

const tf = (timeframe: string, status: OppTfInfo["status"], n: number): OppTfInfo => ({ timeframe, status, n_bars: n, last_ts: 1_790_000_000, stale_bars: 0, derived_from: null, reason: status === "completed" ? null : "no stored candles", reused: false });
const summary = (ranking: Opportunity[], over: Partial<OppSummary> = {}): OppSummary => ({
  scan: { id: 5, status: "completed", trigger: "manual", started_at: NOW, finished_at: NOW, config_version: "t", summary: {
    instruments_requested: 4, instruments_scanned: 2, instruments_unavailable: ["US30", "USOIL"], timeframes_completed: 20, timeframes_total: 28,
    opportunities_actionable: ranking.filter((r) => r.direction !== "WAIT").length, opportunities_watchlist: ranking.filter((r) => r.status === "watchlist").length,
    wait: ranking.filter((r) => r.direction === "WAIT").length, data_freshness: { max_stale_bars: 0, median_stale_bars: 0 }, latest_candle_ts: 1_790_000_000 } },
  running_scan: null, next_scan: { enabled: false, interval_minutes: 0, next_run_estimate: null, note: "" }, score_label: "Evidence Score — Not Win Probability",
  styles: (["scalping", "intraday", "swing", "long_term"] as const).map((style) => ({
    style, label: style, scope: "", setup_timeframes: ["5m"], best: ranking.find((r) => r.style === style && r.rank !== null) ?? null,
    fallback_wait: ranking.find((r) => r.style === style) ?? null })),
  ranking,
  instruments: [
    { symbol: "BTCUSDT", status: "scanned", provider: "binance", provider_status: "active", timeframes: [{ ...tf("1H", "completed", 2500), view: { trend: 1, bias: 1, last_break: "BOS:bullish", last_break_bars_ago: 4, zone: "discount", range_position: 0.3, summary: "bullish structure, last BOS bullish 4 bars ago", last_close: 100, atr: 1 } }, { ...tf("4H", "completed", 800), view: { trend: -1, bias: -1, last_break: null, last_break_bars_ago: null, zone: "premium", range_position: 0.8, summary: "bearish structure", last_close: 100, atr: 1 } }, tf("1m", "insufficient_data", 0), tf("15m", "failed", 0)] },
    { symbol: "US30", status: "unavailable", reason: "OANDA_API_TOKEN is not configured (no verified data source for this instrument)" },
    { symbol: "USOIL", status: "unavailable", reason: "OANDA_API_TOKEN is not configured (no verified data source for this instrument)" },
  ],
  ...over,
});

const detail = (o: Opportunity, over: Partial<OpportunityDetail["evidence"]> = {}): OpportunityDetail => ({
  ...o, status_history: [{ status: "waiting_for_confirmation", at: NOW, note: { created: true } }],
  style_profile: { min_rr: 2, min_evidence: 55, horizon_bars: 24, max_cost_r: 0.1, label: "Swing", scope: "x" },
  evidence: {
    actionable: o.actionable, note: null, scope: "Technical setup on 1H-1D candles", symbol: o.symbol, provider: "twelve_data", lean: "bullish", wait_reasons: o.wait_reasons,
    score_label: "Evidence Score — Not Win Probability", thesis: "4H structure is bullish (last BOS bullish, 6 bars ago). Higher timeframes: 1D bullish.",
    validation: { status: "untested", summary: "No out-of-sample validation exists for XAUUSD swing on 4H", experiment_id: null },
    score: { score: 61, uncapped_score: 72, label: "Evidence Score — Not Win Probability", calibrated: false, method_version: "t", note: "Weighted evidence quality.",
      cap: { status: "untested", max_score: 65, applied: true, reason: "strategy validation status 'untested' limits the score to 65" },
      components: [{ name: "htf_alignment", weight: 0.16, raw: 1, points: 16, detail: "1D: bullish" }, { name: "strategy_validation", weight: 0.1, raw: 0.25, points: 2.5, detail: "untested" }],
      penalties: [{ name: "weak_sample", points: -4, detail: "62 historical analogues (< 100)" }] },
    analogues: { available: true, n_obs: 62, sample_quality: "limited", horizon_bars: 24, horizons: [6, 12, 24], tp_atr: 2.5, sl_atr: 1, tp_first: { k: 20, n: 62, frequency: 0.32, ci_low: 0.22, ci_high: 0.44 },
      base_rate: { k: 600, n: 2400, frequency: 0.25, ci_low: 0.23, ci_high: 0.27 }, edge_vs_base: 0.07, edge_within_noise: true,
      forward_return_atr: { "6": { mean: 0.1, ci_low: 0, ci_high: 0.2, median: 0.1, pct_positive: 0.5, n: 62 }, "12": null, "24": null }, mfe_atr: { mean: 1.4, ci_low: 1, ci_high: 1.8, median: 1.2, pct_positive: 1, n: 62 }, mae_atr: null,
      neighbors: [{ ts: 1_700_000_000, similarity: 0.82, timeframe: "4H", forward_return_atr: { "6": 0.4, "12": 0.9, "24": 1.2 }, mfe_atr: 2.1, mae_atr: 0.6, outcome: "tp_first" }] },
    setup: { direction: o.side ?? "BUY", setup_type: "trend_pullback", status: "waiting_for_confirmation", entry_low: 3900.5, entry_high: 3920.25, entry_ref: 3920.25, stop_loss: 3880.1, invalidation: 3885,
      targets: [{ label: "TP1", price: 3990, rr: 2.4, basis: "swing_high" }, { label: "TP2", price: 4040, rr: 3.5, basis: "swing_high" }], risk_reward: 2.4,
      poi: { kind: "order_block", low: 3900.5, high: 3920.25, ts: 1_700_000_000 }, confirmations: [], conditions: ["Price trades into the entry zone 3900.5 - 3920.25"], warnings: [],
      reasoning: { entry: "BUY zone is an order block; entry reference is its upper edge.", stop: "Stop below the zone plus 0.25 ATR.", targets: ["TP1 3990 (2.40R): swing high"] }, cost_r: 0.03, trigger_ts: null },
    multi_timeframe: [
      { timeframe: "4H", status: "completed", role: "setup", relevant_to_style: true, reason: null, n_bars: 2500, derived_from: "1H", stale_bars: 0, summary: "bullish structure", stance: "supports" },
      { timeframe: "1D", status: "completed", role: "intermediate", relevant_to_style: true, reason: null, n_bars: 2500, derived_from: null, stale_bars: 0, summary: "bearish structure", stance: "opposes" },
      { timeframe: "1M", status: "insufficient_data", role: "context", relevant_to_style: false, reason: "no stored candles", n_bars: 0, derived_from: null, stale_bars: null },
    ],
    structure: { timeframe: "4H", summary: "bullish structure, last BOS bullish 6 bars ago", last_break: "BOS:bullish", last_break_bars_ago: 6, zone: "discount", range_position: 0.3,
      notable_events: [{ kind: "bos", direction: "bullish", ts: 1, price: 3950, evidence: "close above swing high" }], live_zones: [], levels: [] },
    candlesticks: [], risks: { opposing_evidence: ["1D structure is bearish, opposite to the trade"], warnings: ["analogue sample is limited (n=62)"] },
    chart: { timeframe: "4H", zones: [{ kind: "order_block", direction: "bullish", from: 1_700_003_600, low: 3900.5, high: 3920.25 }], levels: [], trendlines: [], markers: [], analogue_markers: [] },
    data: { setup_timeframe: "4H", n_bars: 2500, stale_bars: 0, derived_from: "1H", last_bar: NOW, volume_available: false }, ...over,
  },
});

const VALIDATION = {
  meta: {}, note: "x", reference_backtests: [{ id: 3, symbol: "XAUUSD", strategy: "decision_engine", timeframe: "1H", created_at: NOW, metrics: { n_trades: 120, total_return_pct: -12.1, profit_factor: 0.73, max_drawdown_pct: 15, win_rate: 0.3, expectancy_r: -0.2, sharpe_annualized: null } }],
  results: [{ symbol: "XAUUSD", style: "swing", timeframe: "4H", status: "negative", summary: "OOS CI below zero", experiment_id: 60, oos: { n_trades: 140, expectancy_r: -0.21, win_rate: 0.3, profit_factor: 0.7 }, oos_gross_zero_cost: { expectancy_r: -0.05 } }],
};
const base = {
  "GET /api/v1/opportunities/validation": VALIDATION,
  "GET /api/v1/market/instruments": INSTRUMENTS,
  "GET /api/v1/market/candles": CANDLES,
  "GET /api/v1/health": { status: "ok", version: "0.1.0", env: "test", time: "", mode: "analysis_only", components: {} },
};

beforeEach(() => useSettings.setState({ symbol: "BTCUSDT", timeframe: "1H", experimentalMode: false }));
afterEach(() => vi.unstubAllGlobals());

describe("navigation", () => {
  it("places Signals directly below Overview, then Paper Trading, then Trade Opportunities", () => {
    expect(NAV[0].label).toBe("Overview");
    expect(NAV[1]).toMatchObject({ label: "Signals", href: "/signals" });
    expect(NAV[2]).toMatchObject({ label: "Paper Trading", href: "/paper" });
    expect(NAV[3]).toMatchObject({ label: "Active Trades", href: "/active" });
    expect(NAV[4]).toMatchObject({ label: "Trade Opportunities", href: "/opportunities" });
  });
});

describe("Trade Opportunities page", () => {
  it("shows a loading skeleton first, then the real summary", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([BUY]), [`GET /api/v1/opportunities/${BUY.id}`]: detail(BUY) });
    const { container } = renderWithClient(<OpportunitiesPage />);
    expect(screen.queryByTestId("opp-summary")).not.toBeInTheDocument();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(await screen.findByTestId("opp-summary")).toBeInTheDocument();
    expect(within(screen.getByTestId("stat-tfs")).getByText("20 / 28")).toBeInTheDocument();
  });

  it("surfaces a backend outage with a retry action instead of a blank page", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("offline"); }));
    renderWithClient(<OpportunitiesPage />);
    expect((await screen.findAllByText("Backend unreachable", {}, { timeout: 8000 })).length).toBeGreaterThan(0); // the hook retries transient failures first
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  }, 12000);

  it("explains the empty state before any scan exists and never invents opportunities", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": { scan: null, running_scan: null, next_scan: { enabled: false, interval_minutes: 0, next_run_estimate: null, note: "" }, score_label: "x", styles: [], ranking: [], instruments: [] } });
    renderWithClient(<OpportunitiesPage />);
    expect(await screen.findByText("No scan has been run yet")).toBeInTheDocument();
    expect(screen.queryByTestId("opp-table")).not.toBeInTheDocument();
  });

  it("reports NO TRADE as a valid result, with the reason and the next condition spelled out", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([WAIT, LONG]), "GET /api/v1/opportunities/14": detail(WAIT, { actionable: false, setup: null, score: null, thesis: undefined }) });
    renderWithClient(<OpportunitiesPage />);
    expect(await screen.findByText(/NO TRADE and WAIT are valid results/i)).toBeInTheDocument();
    const card = screen.getByTestId("style-scalping");
    expect(within(card).getByTestId("call-badge")).toHaveTextContent(/^NO TRADE$/);
    expect(within(card).getByText(/No setup qualifies: 1m: latest candle is 90 bars old/)).toBeInTheDocument();
    expect(within(card).getByText(/Next: 1m: latest candle is 90 bars old; too stale to scalp/)).toBeInTheDocument();
    expect(within(card).queryByText(/\/ 100/)).not.toBeInTheDocument(); // no score is invented for a non-setup
  });

  it("lists every setup with the backend decision; unvalidated setups never show entry, stop or targets", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([BUY, SELL, WATCH, WAIT]), "GET /api/v1/opportunities/11": detail(BUY) });
    renderWithClient(<OpportunitiesPage />);
    const table = await screen.findByTestId("opp-table");
    const buy = within(within(table).getByTestId("opp-row-11"));
    expect(buy.getByTestId("call-badge")).toHaveTextContent("WAIT — CONFIRMATION PENDING");
    expect(buy.getByText("Waiting for confirmation")).toBeInTheDocument(); // the technical status, kept separate from the decision
    expect(buy.getByText("Not validated")).toBeInTheDocument();
    expect(buy.getByText("61")).toBeInTheDocument();
    expect(buy.getAllByText("—").length).toBeGreaterThanOrEqual(6); // entry, stop, TP1-3 and R/R withheld
    const sell = within(within(table).getByTestId("opp-row-12"));
    expect(sell.getByTestId("call-badge")).toHaveTextContent("WAIT — UNVALIDATED SETUP"); // technically triggered, but not validated: never ENTER
    expect(sell.getByText("Entry triggered")).toBeInTheDocument();
    const watch = within(within(table).getByTestId("opp-row-13"));
    expect(watch.getByTestId("call-badge")).toHaveTextContent("WAIT — SETUP DEVELOPING");
    expect(watch.getByText("Watchlist")).toBeInTheDocument();
    expect(within(table).getByTestId("opp-row-14")).toHaveTextContent("NO TRADE");
    for (const t of ["3,880.10", "3,990.00", "77,400.00", "76,400.00", "3,895.00"]) expect(table).not.toHaveTextContent(t);
    expect(within(table).getByText(/Evidence Score/)).toHaveAttribute("title", "Evidence Score — Not Win Probability");
    expect(screen.getByText(/not a win probability/i)).toBeInTheDocument();
    expect(screen.queryByText(/EXECUTE NOW/)).toBeNull();
    expect(screen.queryByText(/NO TRADE and WAIT are valid results/i)).not.toBeInTheDocument(); // there ARE technical setups
  });

  it("shows every level only when the backend decision is ENTER", async () => {
    const enter = { ...SELL, call: CALL_OPP_SELL_ENTER, validation_status: "validated" as const };
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([enter, WATCH]), "GET /api/v1/opportunities/12": detail(enter) });
    renderWithClient(<OpportunitiesPage />);
    const row = within(within(await screen.findByTestId("opp-table")).getByTestId("opp-row-12"));
    expect(row.getByTestId("call-badge")).toHaveTextContent(/^ENTER$/);
    for (const t of ["77,000.00 – 77,100.00", "77,400.00", "76,400.00", "76,000.00", "2.00R"]) expect(row.getByText(t, { exact: false })).toBeInTheDocument();
    expect(row.getAllByText("—").length).toBeGreaterThan(0); // TP3 absent: shown as an em dash, never made up
  });

  it("shows what every timeframe is doing even when no setup qualifies", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([WAIT]), "GET /api/v1/opportunities/14": detail(WAIT, { setup: null, score: null }) });
    renderWithClient(<OpportunitiesPage />);
    const m = await screen.findByTestId("tf-matrix");
    const row = within(m).getByText("BTCUSDT").closest("tr")!;
    const cells = Array.from(row.querySelectorAll("td[data-cell]")).map((c) => c.getAttribute("data-cell"));
    expect(cells.filter((c) => c === "up")).toHaveLength(1); // 1H bullish
    expect(cells.filter((c) => c === "down")).toHaveLength(1); // 4H bearish
    expect(cells.filter((c) => c === "na").length).toBe(12); // 1m insufficient, 15m failed and the 10 timeframes with no data: shown as a dash, never guessed
    expect(within(m).getByText("D")).toBeInTheDocument();
    expect(within(m).getByText("P")).toBeInTheDocument();
    expect(within(m).getByText(/not a signal/i)).toBeInTheDocument();
  });

  it("shows unsupported / unavailable instruments and failed timeframes clearly, with no prices", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([WAIT]), "GET /api/v1/opportunities/14": detail(WAIT, { setup: null, score: null }) });
    renderWithClient(<OpportunitiesPage />);
    const panel = await screen.findByTestId("instrument-status");
    const us30 = within(panel).getByText("US30").closest("details")!;
    expect(within(us30).getByText("unavailable")).toBeInTheDocument();
    expect(within(us30).getByText(/OANDA_API_TOKEN is not configured/)).toBeInTheDocument();
    expect(us30.textContent).not.toMatch(/\d{2},\d{3}/);
    const btc = within(panel).getByText("BTCUSDT").closest("details")!;
    expect(within(btc).getAllByText("Completed").length).toBe(2);
    expect(within(btc).getByText("Insufficient data")).toBeInTheDocument();
    expect(within(btc).getByText("Failed")).toBeInTheDocument();
    expect(within(btc).getByText("2/14 timeframes", { exact: false })).toBeInTheDocument();
  });

  it("starts a scan and reflects a deduplicated (already running) scan", async () => {
    const { calls } = mockApi({
      ...base, "GET /api/v1/opportunities/summary": summary([WAIT]), "GET /api/v1/opportunities/14": detail(WAIT, { setup: null, score: null }),
      "POST /api/v1/opportunities/scan": { id: 9, status: "running", poll_url: "/api/v1/opportunities/scans/9", deduplicated: true },
    });
    renderWithClient(<OpportunitiesPage />);
    await userEvent.click(await screen.findByTestId("run-scan"));
    expect(await screen.findByText(/already running \(#9\)/)).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/v1/opportunities/scan")).toBe(true);
  });

  it("shows a scan request failure instead of silently doing nothing", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([WAIT]), "GET /api/v1/opportunities/14": detail(WAIT, { setup: null, score: null }),
      "POST /api/v1/opportunities/scan": { error: { code: "unauthorized", message: "Invalid API key" } } }, { "POST /api/v1/opportunities/scan": 401 });
    renderWithClient(<OpportunitiesPage />);
    await userEvent.click(await screen.findByTestId("run-scan"));
    expect(await screen.findByText("Invalid API key")).toBeInTheDocument();
  });

  it("opens the full evidence for a selected opportunity: decision, chart, score breakdown, analogues, risks, invalidation; levels withheld", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([BUY, WAIT]), "GET /api/v1/opportunities/11": detail(BUY) });
    renderWithClient(<OpportunitiesPage />);
    const d = await screen.findByTestId("opp-detail"); // top-ranked opportunity is opened by default
    const card = await within(d).findByTestId("call-card");
    expect(within(card).getByTestId("call-decision")).toHaveTextContent("WAIT — CONFIRMATION PENDING");
    expect(within(card).getByTestId("call-next")).toHaveTextContent("A confirmation signal in the BUY direction");
    expect(within(d).queryByTestId("levels")).toBeNull();
    expect(within(d).queryByTestId("sec-entry")).toBeNull();
    await waitFor(() => expect(within(d).getByTestId("candle-chart")).toHaveTextContent("lines: ;"));
    expect(within(d).getByTestId("candle-chart")).toHaveTextContent("zones: 1"); // the detected order block only: no entry zone drawn
    const score = within(d).getByTestId("score-panel");
    expect(within(score).getByText("61")).toBeInTheDocument();
    expect(within(score).getByText("Evidence Score — Not Win Probability")).toBeInTheDocument();
    expect(within(score).getByText("capped from 72")).toBeInTheDocument();
    expect(within(score).getByText(/Penalty: weak sample/)).toBeInTheDocument();
    expect(within(d).getByText(/not the probability that this trade will succeed/i)).toBeInTheDocument();
    expect(within(d).getByText(/within sampling noise/i)).toBeInTheDocument();
    const mtf = within(within(d).getByTestId("sec-mtf"));
    expect(mtf.getByText("opposes")).toBeInTheDocument();
    expect(mtf.getByText("Insufficient data")).toBeInTheDocument();
    expect(within(within(d).getByTestId("sec-risks")).getByText(/1D structure is bearish/)).toBeInTheDocument();
    expect(within(within(d).getByTestId("sec-invalid")).getByText(/Price closes beyond 3885/)).toBeInTheDocument();
    expect(within(d).getByText(/No out-of-sample validation exists/)).toBeInTheDocument();
  });

  it("experimental mode shows the hypothetical levels, chart lines and reasoning, clearly marked", async () => {
    useSettings.setState({ experimentalMode: true });
    const x = { ...BUY, call: CALL_OPP_BUY_X };
    const api = mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([x, WAIT]), "GET /api/v1/opportunities/11": detail(x) });
    renderWithClient(<OpportunitiesPage />);
    const d = await screen.findByTestId("opp-detail");
    await waitFor(() => expect(within(d).getByTestId("levels")).toHaveTextContent("HYPOTHETICAL — UNVALIDATED"));
    expect(within(d).getByText("TP2 · 3.50R")).toBeInTheDocument();
    expect(within(d).getByTestId("call-hypothetical")).toHaveTextContent("3,880.10");
    expect(within(d).getByTestId("call-decision")).toHaveTextContent("WAIT — CONFIRMATION PENDING"); // the decision does not change
    await waitFor(() => expect(within(d).getByTestId("candle-chart")).toHaveTextContent("BUY entry,SL,TP1,TP2,Invalidation"));
    expect(within(d).getByTestId("candle-chart")).toHaveTextContent("zones: 2"); // detected order block + entry zone
    expect(within(within(d).getByTestId("sec-entry")).getByText(/entry reference is its upper edge/)).toBeInTheDocument();
    expect(within(within(d).getByTestId("sec-invalid")).getByText(/closing below 3,885\.00/)).toBeInTheDocument();
    expect(api.fn.mock.calls.some(([u]) => String(u).includes("experimental=true"))).toBe(true);
  });

  it("shows validation results and the user's existing negative backtests unchanged", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([WAIT]), "GET /api/v1/opportunities/14": detail(WAIT, { setup: null, score: null }) });
    renderWithClient(<OpportunitiesPage />);
    const panel = await screen.findByTestId("validation-panel");
    await waitFor(() => expect(within(panel).getByText("negative OOS")).toBeInTheDocument());
    expect(within(panel).getByText("-12.1%")).toBeInTheDocument();
    expect(within(panel).getByText("0.73")).toBeInTheDocument();
  });

  it("switches the detail when another row is selected", async () => {
    mockApi({ ...base, "GET /api/v1/opportunities/summary": summary([BUY, SELL]), "GET /api/v1/opportunities/11": detail(BUY), "GET /api/v1/opportunities/12": detail(SELL) });
    renderWithClient(<OpportunitiesPage />);
    await screen.findByTestId("opp-detail");
    await userEvent.click(screen.getByTestId("opp-row-12"));
    await waitFor(() => expect(within(screen.getByTestId("opp-detail")).getByTestId("call-card")).toHaveTextContent("BTCUSDT · SELL · 30m"));
  });
});

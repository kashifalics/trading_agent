import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSettings } from "@/lib/store";
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

beforeEach(() => useSettings.setState({ symbol: "BTCUSDT", timeframe: "1H" }));
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

  it("surfaces a backend outage with a retry action instead of blank cards", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("offline"); }));
    renderWithClient(<DashboardPage />);
    expect((await screen.findAllByText("Backend unreachable")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /retry/i }).length).toBeGreaterThan(0);
  });
});

describe("Chart analysis workflow", () => {
  it("runs an analysis job, polls to completion and shows the plan", async () => {
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
    await waitFor(() => expect(within(panel).getByText("BUY")).toBeInTheDocument(), { timeout: 6000 });
    expect(within(panel).getByText("101.00")).toBeInTheDocument(); // stop loss from backend
    expect(screen.getByTestId("candle-chart")).toHaveTextContent("BUY entry,SL,TP1,TP2");
    const run = calls.find((c) => c.key === "POST /api/v1/analysis/run");
    expect(run?.body).toMatchObject({ symbol: "BTCUSDT", timeframe: "1H", lookback_bars: 1500, auto_sync: true });
  }, 15000);

  it("shows WAIT with reasons and no trade levels", async () => {
    mockApi({
      ...base,
      "GET /api/v1/market/candles": CANDLES,
      "GET /api/v1/predictions": { items: [{ id: 9, analysis_id: 7, symbol: "BTCUSDT", timeframe: "1H", decision: "WAIT", created_at: "2026-10-31T20:00:00Z", as_of_ts: "2026-10-31T20:00:00Z" }], total: 1, limit: 10, offset: 0 },
      "GET /api/v1/analysis/7": analysis("WAIT"),
    });
    renderWithClient(<ChartPage />);
    const panel = await screen.findByTestId("decision-panel");
    await waitFor(() => expect(within(panel).getByText(/below the \+\/-0.35 threshold/)).toBeInTheDocument());
    expect(within(panel).queryByText(/stop loss/i)).not.toBeInTheDocument();
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
        items: [{ id: 1, analysis_id: 1, symbol: "BTCUSDT", timeframe: "1H", decision: "SELL", entry_low: 100, entry_high: 101, stop_loss: 103, take_profit: [95], risk_reward: 2.5, data_quality_score: 0.9, outcome: "open", as_of_ts: "2026-10-31T20:00:00Z" }],
        total: 1, limit: 20, offset: 0,
      },
    });
    renderWithClient(<PredictionsPage />);
    expect(await screen.findByText("SELL")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Filter decision"), "BUY");
    await waitFor(() => expect(calls.some((c) => c.key === "GET /api/v1/predictions")).toBe(true));
  });
});

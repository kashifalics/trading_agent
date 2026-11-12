import { expect, test, type Page } from "@playwright/test";
import { CANDLES, INSTRUMENTS, QUOTES, analysis } from "../src/test/fixtures";

const API = "http://localhost:8000/api/v1";
const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body), headers: { "access-control-allow-origin": "*" } });

// A fresh paper account with no recorded signals yet: the state production starts in.
const PAPER_EMPTY = {
  generated_at: "2026-11-07T12:00:00Z",
  account: {
    id: 1, name: "Paper account", start_balance: 10000, risk_pct: 0.5, max_open_positions: 5, max_daily_loss_pct: 2, is_active: true,
    created_at: "2026-11-07T00:00:00Z", balance: 10000, start_of_day_balance: 10000, today_pnl: 0, live_trades: 0, can_trade: true, blocked_reason: null,
    risk_per_trade: 50, equity: 10000, unrealized_pnl: 0, open_risk: 0, return_pct: 0, metrics: { n_trades: 0 }, max_drawdown: 0, equity_curve: [], skipped_signals: 0,
  },
  forward: {
    n_trades: 0, verdict: { status: "collecting", n: 0, needed: 100, summary: "0 of 100 closed trades: too few to tell an edge from luck, no conclusion yet" },
    counts: { pending: 0, open: 0, closed: 0, cancelled: 0, missed: 0, expired: 0, skipped: 0 }, signals_recorded: 0, limit_fill_rate: null, since: null, equity_curve: [],
  },
  backtest: { n_trades: 414, expectancy_r: -0.19, note: "historical replay" },
  breakdowns: { series: [], symbol: [], timeframe: [], setup_type: [], score_band: [], direction: [], order_type: [], session: [] },
  open: [], pending: [], recent: [],
  worker: { enabled: true, interval_s: 60, running: false, cycles: 3, last_cycle_at: "2026-11-07T11:59:30Z", last_duration_s: 11.2, last_results: [], last_error: null },
  method: ["Every technically complete setup is recorded when the backend first sees it (immediate entry -> market order, limit plan -> limit order), whatever the customer decision: this is the forward test of the unvalidated rules; nothing is backfilled."],
  disclaimer: "Paper trading: simulated orders on live candles, no broker and no real money.",
};

async function mockBackend(page: Page) {
  const empty = { items: [], total: 0, limit: 25, offset: 0 };
  let polls = 0;
  await page.route(`${API}/**`, async (route) => {
    const u = new URL(route.request().url());
    const key = `${route.request().method()} ${u.pathname.replace("/api/v1", "")}`;
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" } });
    const table: Record<string, unknown> = {
      "GET /health": { status: "ok", version: "0.1.0", env: "test", time: "", mode: "analysis_only", components: { ocr_tesseract: false } },
      "GET /market/instruments": INSTRUMENTS,
      "GET /market/quotes": QUOTES,
      "GET /market/timeframes": [],
      "GET /market/coverage": [],
      "GET /market/providers": [],
      "GET /market/candles": CANDLES,
      "GET /predictions": empty,
      "GET /predictions/stats": { total: 0, by_decision: {}, by_outcome: {}, resolved: 0, tp_first_rate: null, tp_first_ci: null, per_instrument: {}, note: "" },
      "GET /analysis": empty,
      "GET /models": { ...empty, limit: 50 },
      "GET /backtests": empty,
      "GET /backtests/strategies": [{ id: "decision_engine", description: "" }],
      "GET /patterns": { symbol: "BTCUSDT", timeframe: "1H", provider: "binance", n_bars: 0, events: [], swings: [], message: "Not enough stored candles; sync data first." },
      "GET /patterns/definitions": { candlestick: { hammer: "Lower wick >= 2x body" }, price_action: {}, note: "Detections are descriptive." },
      "GET /watchlists": [],
      "POST /analysis/run": { id: 7, status: "queued", poll_url: "/api/v1/analysis/7" },
      "GET /signals": { items: [], generated_at: "2026-11-07T12:00:00Z", config_version: "test", disclaimer: "Analysis only." },
      "GET /paper/summary": PAPER_EMPTY,
      "GET /paper/trades": { ...empty, limit: 200 },
    };
    if (key === "GET /analysis/7") return route.fulfill(json(analysis("BUY", ++polls < 2 ? "running" : "completed")));
    if (key in table) return route.fulfill(json(table[key], key.startsWith("POST") ? 202 : 200));
    return route.fulfill(json({ error: { code: "not_found", message: `unmocked ${key}` } }, 404));
  });
}

const ROUTES = ["/", "/signals", "/paper", "/gold-research", "/chart", "/scanner", "/predictions", "/patterns", "/backtesting", "/performance", "/watchlists", "/data-sources", "/models", "/settings"];

test.beforeEach(async ({ page }) => mockBackend(page));

test("dashboard is honest about unsupported and unconfigured instruments", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("quote-BTCUSDT")).toContainText("77,488.75");
  await expect(page.getByTestId("quote-US30")).toContainText("No data source configured");
  await expect(page.getByTestId("quote-XAUUSD")).toContainText("API key required");
  await expect(page.getByText("No predictions yet")).toBeVisible();
});

test("critical workflow: run an analysis and read the decision", async ({ page }) => {
  await page.goto("/chart");
  await page.getByRole("button", { name: /run analysis/i }).click();
  const panel = page.getByTestId("decision-panel");
  await expect(panel.getByTestId("call-decision")).toHaveText("WAIT — UNVALIDATED SETUP", { timeout: 10_000 });
  await expect(panel.getByTestId("call-validation")).toContainText("Not validated");
  await expect(panel).not.toContainText("101.00"); // the technical stop is withheld: the rules are not validated
  await expect(page.getByText("EXECUTE NOW")).toHaveCount(0);
  await expect(page.getByTestId("confidence-panel")).toContainText("no probability is shown");
});

test("every page renders without horizontal overflow or console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const path of ROUTES) {
    await page.goto(path);
    await expect(page.locator("main h1")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${path} overflows horizontally`).toBeLessThanOrEqual(1);
  }
  expect(errors).toEqual([]);
});


test("login journey: the server asks for a key, Settings verifies it, then the analysis pages load with it", async ({ page }) => {
  // Registered after mockBackend, so these handlers take precedence for /health and /auth/status.
  await page.route(`${API}/health`, (route) =>
    route.fulfill(json({ status: "ok", version: "0.1.0", env: "production", time: "", mode: "analysis_only", components: {}, auth_required: true })));
  await page.route(`${API}/auth/status`, (route) =>
    route.request().headers()["x-api-key"] === "ati_e2e"
      ? route.fulfill(json({ authenticated: true, auth_required: true, mode: "analysis_only", key_used: true }))
      : route.fulfill(json({ error: { code: "unauthorized", message: "Invalid API key" } }, 401)));
  await page.goto("/");
  const banner = page.getByTestId("api-key-banner");
  await expect(banner).toContainText("requires a platform API key");
  await banner.getByRole("link", { name: /enter it in settings/i }).click();
  await expect(page.locator("main h1")).toHaveText("Settings");
  await page.getByLabel(/Platform API key/).fill("ati_wrong");
  await page.getByRole("button", { name: /save & verify/i }).click();
  await expect(page.getByTestId("key-check")).toHaveText("The server rejected this key.");
  await page.getByLabel(/Platform API key/).fill("ati_e2e");
  await page.getByRole("button", { name: /save & verify/i }).click();
  await expect(page.getByTestId("key-check")).toHaveText("Key accepted by the server.");
  // A full page load must send the saved key on its very first requests (regression: they used to go out before rehydration).
  const firstSignals = page.waitForRequest((r) => r.url().endsWith("/api/v1/signals"));
  await page.goto("/signals");
  expect((await firstSignals).headers()["x-api-key"]).toBe("ati_e2e");
  await expect(page.locator("main h1")).toHaveText("Signals");
  await expect(page.getByTestId("api-key-banner")).toHaveCount(0);
  await expect(page.getByText(/Every instrument and timeframe gets one decision/)).toContainText("WAIT — UNVALIDATED SETUP");
});

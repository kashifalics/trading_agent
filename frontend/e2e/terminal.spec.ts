import { expect, test, type Page } from "@playwright/test";
import { CANDLES, INSTRUMENTS, QUOTES, analysis } from "../src/test/fixtures";

const API = "http://localhost:8000/api/v1";
const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body), headers: { "access-control-allow-origin": "*" } });

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
    };
    if (key === "GET /analysis/7") return route.fulfill(json(analysis("BUY", ++polls < 2 ? "running" : "completed")));
    if (key in table) return route.fulfill(json(table[key], key.startsWith("POST") ? 202 : 200));
    return route.fulfill(json({ error: { code: "not_found", message: `unmocked ${key}` } }, 404));
  });
}

const ROUTES = ["/", "/chart", "/scanner", "/predictions", "/patterns", "/backtesting", "/performance", "/watchlists", "/data-sources", "/models", "/settings"];

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
  await expect(panel.getByText("BUY", { exact: true }).first()).toBeVisible({ timeout: 10_000 });
  await expect(panel).toContainText("101.00");
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

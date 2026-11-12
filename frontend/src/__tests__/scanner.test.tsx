import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ScannerPage from "@/app/(terminal)/scanner/page";
import type { SignalsSummary } from "@/lib/signal-types";
import { CALL_EMPTY, CALL_WATCH } from "@/test/calls";
import { INSTRUMENTS } from "@/test/fixtures";
import { mockApi, renderWithClient } from "@/test/utils";

const now = new Date().toISOString();
const SUMMARY: SignalsSummary = {
  generated_at: now, config_version: "x", disclaimer: "Analysis only.",
  items: [
    { symbol: "XAUUSD", status: "ok", call: CALL_WATCH, as_of: now, tfs: [
      { timeframe: "3m", decision: "HOLD", label: "HOLD — PAPER TRADE OPEN", headline: "The paper-trading test already holds a SELL trade", direction: "SELL", score: 61, state: "SETUP_DEVELOPING", unrealized_r: 8.4 },
      { timeframe: "4H", decision: "NO TRADE", label: "NO TRADE — CONDITION FAILED", headline: "Stop-loss: too far", direction: "SELL", score: 66, state: "WATCHLIST", unrealized_r: null },
      { timeframe: "1D", decision: "WAIT", label: "WAIT — PRICE NOT AT ENTRY ZONE", headline: "A SELL setup is waiting", direction: "SELL", score: 64, state: "SETUP_DEVELOPING", unrealized_r: null }] },
    { symbol: "BTCUSDT", status: "unavailable", reason: "no stored candles", call: CALL_EMPTY, tfs: [] },
  ],
};

describe("Market Scanner", () => {
  it("shows the live decision of every instrument and timeframe, each linking to its checklist", async () => {
    mockApi({ "GET /api/v1/signals": SUMMARY, "GET /api/v1/market/instruments": INSTRUMENTS, "GET /api/v1/predictions": { items: [], total: 0, limit: 200, offset: 0 } });
    renderWithClient(<ScannerPage />);
    const matrix = await screen.findByTestId("live-matrix");
    await within(matrix).findByTestId("matrix-XAUUSD"); // the card shows a skeleton until the decisions arrive
    expect(within(matrix).getAllByRole("row")).toHaveLength(3); // header + every instrument
    expect(within(matrix).getAllByRole("columnheader")).toHaveLength(15); // instrument + 14 timeframes
    const held = within(matrix).getByTestId("cell-XAUUSD-3m");
    expect(held).toHaveTextContent("HOLD");
    expect(held).toHaveTextContent("SELL +8.4R"); // a held paper trade shows its open result
    expect(held).toHaveAttribute("href", "/signals?symbol=XAUUSD&tf=3m");
    expect(within(matrix).getByTestId("cell-XAUUSD-1D")).toHaveTextContent(/^WAITs*PRICE NOT AT ENTRY ZONEs*SELL 64$/);
    expect(matrix).toHaveTextContent("1 held paper trades · 1 WAIT · 1 NO TRADE · 0 ENTER");
    expect(within(matrix).getByTestId("matrix-BTCUSDT")).toHaveTextContent("no data yet");
    expect(screen.getByText("Deep analysis (stored, run on demand)")).toBeInTheDocument();
  });
});

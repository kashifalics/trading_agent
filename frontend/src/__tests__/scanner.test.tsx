import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ScannerPage from "@/app/(terminal)/scanner/page";
import { ENGINE_SUMMARY } from "@/test/engine";
import { INSTRUMENTS } from "@/test/fixtures";
import { mockApi, renderWithClient } from "@/test/utils";

describe("Market Scanner", () => {
  it("shows the strategy engine's live action for every instrument and timeframe", async () => {
    mockApi({ "GET /api/v1/engine": ENGINE_SUMMARY, "GET /api/v1/market/instruments": INSTRUMENTS, "GET /api/v1/predictions": { items: [], total: 0, limit: 200, offset: 0 } });
    renderWithClient(<ScannerPage />);
    const matrix = await screen.findByTestId("live-matrix");
    await within(matrix).findByTestId("matrix-XAUUSD"); // the card shows a skeleton until the actions arrive
    expect(within(matrix).getAllByRole("row")).toHaveLength(5); // header + every instrument
    expect(within(matrix).getAllByRole("columnheader")).toHaveLength(12); // instrument + 11 signal timeframes
    expect(within(matrix).getByTestId("cell-XAUUSD-1H")).toHaveTextContent("BUY");
    expect(within(matrix).getByTestId("cell-XAUUSD-1H")).toHaveTextContent("Trend-following · 3.2R");
    expect(within(matrix).getByTestId("cell-EURUSD-1H")).toHaveTextContent("WAIT FOR SELL");
    expect(within(matrix).getByTestId("cell-GBPUSD-1H")).toHaveTextContent("NO TRADE");
    expect(matrix).toHaveTextContent("1 BUY/SELL · 1 WAIT FOR ENTRY");
    expect(screen.getByText("Deep analysis (stored, run on demand)")).toBeInTheDocument();
  });
});

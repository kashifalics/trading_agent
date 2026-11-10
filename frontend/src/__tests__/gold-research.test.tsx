import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import GoldResearchPage from "@/app/(terminal)/gold-research/page";
import { mockApi, renderWithClient } from "@/test/utils";

const EXP3 = {
  key: "experiment_3", name: "Experiment 3", description: "Well-powered structural setups", segment: "development: whole training period",
  tests_run: 6, pre_registered: 9, candidates: 0, trials_counted: 1973, report: "docs/reports/XAUUSD_EXPERIMENT3.md",
  rows: [
    { tf: "H1", setup: "E3_broken_level_retest", direction: "long + short", trades: 5205, mean_r: -0.507, control_r: -0.516, edge: 0.009, q: 0.289, candidate: false },
    { tf: "H1", setup: "E2_fvg_displacement_1p5", direction: "long + short", trades: 2237, mean_r: -0.271, control_r: -0.331, edge: 0.06, q: 0.094, candidate: false },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("Gold Research page", () => {
  it("shows every experiment with its real result, losses included, and never a candidate that is not one", async () => {
    mockApi({
      "GET /api/v1/research/gold": { available: true, status: { experiment_3: "done: 0 candidates", final_test: "sealed (not run)" }, experiments: [EXP3] },
      "GET /api/v1/signals/XAUUSD": { symbol: "XAUUSD", status: "unavailable", reason: "no stored candles yet.", plans: [], timeframes: [] },
    });
    renderWithClient(<GoldResearchPage />);
    const card = await screen.findByTestId("experiment-experiment_3");
    expect(within(card).getByText("0 candidates")).toBeInTheDocument();
    expect(within(card).getByText("E3 · broken level retest")).toBeInTheDocument();
    expect(within(card).getByText("-0.507")).toBeInTheDocument();
    expect(within(card).getAllByText("not a candidate")).toHaveLength(2);
    expect(within(card).getByText(/1,973 trials/)).toBeInTheDocument();
    expect(screen.getByText(/experiment 3: done: 0 candidates/)).toBeInTheDocument();
  });
});

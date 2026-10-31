import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ConfidencePanel } from "@/lib/types";
import { ConfidencePanelView, EvidenceList, PlanCard } from "./decision";

const freq = (f: number) => ({ k: 10, n: 50, frequency: f, ci_low: f - 0.1, ci_high: f + 0.1 });
const panel = (over: Partial<ConfidencePanel> = {}): ConfidencePanel => ({
  model_probability: null,
  research_only_model_output: null,
  historical_frequency: { long_tp_before_sl: freq(0.4), short_tp_before_sl: freq(0.2), base_rate_long: freq(0.3), base_rate_short: freq(0.3), n_obs: 50, sufficient: true, label: "historical frequency" },
  analytical_confluence: { score: 0.52, scale: "[-1, +1]", components: [] },
  data_quality: { score: 0.8, issues: ["limited history"] },
  uncertainty: ["no trained ML model"],
  ...over,
});

describe("ConfidencePanelView", () => {
  it("never shows a probability without a validated model", () => {
    render(<ConfidencePanelView panel={panel()} />);
    expect(screen.getByText(/no probability is shown/i)).toBeInTheDocument();
    expect(screen.getByText("not a probability")).toBeInTheDocument();
    expect(screen.getByText(/limited history/)).toBeInTheDocument();
  });

  it("labels research-only model output and keeps it out of the probability slot", () => {
    render(<ConfidencePanelView panel={panel({ research_only_model_output: { p_long_tp_first: 0.9, p_short_tp_first: 0.02, p_neither: 0.08, validation_status: "research_only", note: "excluded from the decision" } })} />);
    expect(screen.getByText("research only")).toBeInTheDocument();
    expect(screen.getByText(/no probability is shown/i)).toBeInTheDocument();
  });

  it("shows calibrated probabilities only when supplied by the backend", () => {
    render(<ConfidencePanelView panel={panel({ model_probability: { p_long_tp_first: 0.41, p_short_tp_first: 0.22, p_neither: 0.37, model_version_id: 3 } })} />);
    expect(screen.getByText("41.0%")).toBeInTheDocument();
    expect(screen.queryByText(/no probability is shown/i)).not.toBeInTheDocument();
  });
});

describe("PlanCard", () => {
  it("explains WAIT with the backend's reasons and no price levels", () => {
    render(<PlanCard decision="WAIT" plan={null} waitReasons={["confluence +0.12 is below the threshold"]} />);
    expect(screen.getByText("WAIT")).toBeInTheDocument();
    expect(screen.getByText(/below the threshold/)).toBeInTheDocument();
    expect(screen.queryByText(/stop loss/i)).not.toBeInTheDocument();
  });

  it("renders entry, stop, targets and risk/reward for a BUY", () => {
    render(<PlanCard decision="BUY" waitReasons={[]} precision={2} plan={{ direction: "BUY", entry_low: 99, entry_high: 101, entry_ref: 100, stop_loss: 97.5, invalidation: 98, targets: [105, 107], risk_reward: 2, target_basis: "fixed_multiple", warnings: [] }} />);
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("97.50")).toBeInTheDocument();
    expect(screen.getByText("105.00")).toBeInTheDocument();
    expect(screen.getByText("1 : 2.00")).toBeInTheDocument();
  });
});

describe("EvidenceList", () => {
  it("flags zero-weight (excluded) evidence and handles empty input", () => {
    const { rerender } = render(<EvidenceList evidence={[{ category: "ml_model", name: "ml_lightgbm", direction: "bullish", weight: 0, score: 0.8, detail: "research-only", ts: null, price: null }]} />);
    expect(screen.getByText("weight 0")).toBeInTheDocument();
    rerender(<EvidenceList evidence={[]} />);
    expect(screen.getByText(/No evidence was computed/)).toBeInTheDocument();
  });
});

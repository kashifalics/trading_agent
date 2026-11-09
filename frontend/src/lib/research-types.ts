// Gold Research dashboard (GET /api/v1/research/gold). Historical research only; final-test figures are never sent.

export interface ResearchPatternRow {
  tf: string;
  pattern: string;
  direction: "long" | "short";
  family: string;
  entry: "market" | "limit";
  trades: number;
  win_rate: number | null;
  mean_r: number | null;
  edge: number | null;
  edge_se: number | null;
  profit_factor: number | null;
  q: number | null;
  status: string;
  stage: number;
  smallest_detectable_edge: number | null;
  validation: { trades: number; mean_r: number | null; edge: number | null; verdict: string } | null;
}

export interface ScenarioCell {
  trades: number;
  mean_r: number;
  edge: number;
}

export interface ModelSummary {
  rows: number;
  features: number;
  best_kind: string;
  comparison: Record<string, { roc_auc?: number; pr_auc?: number; brier_skill?: number; log_loss?: number; ece?: number }>;
  calibrated: { roc_auc?: number; brier_skill?: number; ece?: number };
  top_decile?: { n_trades?: number; expectancy_r?: number; win_rate?: number } | null;
  shuffled_label_auc?: number;
  challenger: string;
  validation: { passed_gate: boolean; gate_failures: string[] } | null;
  champion: string | null;
}

export interface GoldResearch {
  available: boolean;
  generated?: string;
  status: Record<string, string>;
  disclaimer?: string;
  dataset?: {
    source: string | null;
    price: string;
    first_traded_minute: string | null;
    last_minute: string | null;
    m1_candles: number | null;
    traded_coverage_pct: number | null;
    material_gaps: number | null;
    material_gap_minutes: number | null;
    filler_minutes_removed: number | null;
    invalid_candles: number | null;
    duplicates: number | null;
    timeframes: Record<string, { earliest: string; latest: string; bars: number; identical_to_m1_rebuild?: boolean | null }>;
    dukascopy_crosscheck?: Record<string, { candles_compared: number; high_match_pct: number | null; low_match_pct: number | null }> | null;
  };
  split?: {
    train: { start: string; end: string };
    validation: { start: string; end: string };
    test: { start: string; sealed: boolean };
    sha256: string;
  } | null;
  patterns?: {
    segment: string;
    main_test: { target_r: number; hold_candles: number; costs: string } | null;
    stages: number;
    tests: number;
    candidates: ResearchPatternRow[];
    best: ResearchPatternRow[];
    worst: ResearchPatternRow[];
    by_family: Record<string, { tests: number; candidates: number; patterns: number }>;
    status_counts: Record<string, number>;
    all: ResearchPatternRow[];
  } | null;
  scenarios?: ({ segment: string; note: string } & Record<string, Record<string, ScenarioCell> | string>) | null;
  models?: { segment: string; label: string; tfs: Record<string, ModelSummary> } | null;
}

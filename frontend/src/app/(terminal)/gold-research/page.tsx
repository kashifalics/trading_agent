"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState, PageHeader, QueryState, SourceNote } from "@/components/domain/common";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, Stat } from "@/components/ui/card";
import { Tabs } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useGoldResearch, useSignal } from "@/lib/hooks";
import type { GoldResearch, ResearchExperiment, ResearchPatternRow, ScenarioCell } from "@/lib/research-types";

const num = (v: number | null | undefined, d = 2, sign = false) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : `${sign && v > 0 ? "+" : ""}${v.toFixed(d)}`;
const pct = (v: number | null | undefined, d = 0) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(d)}%`);
const day = (s: string | null | undefined) => (s ? s.slice(0, 10) : "–");

function SegmentBadge({ children }: { children: React.ReactNode }) {
  return <Badge variant="info" className="ml-2 align-middle">{children}</Badge>;
}

function StatusBadge({ status }: { status: string }) {
  const v = status === "candidate" || status.startsWith("CONFIRMED") ? "buy" : status.startsWith("no edge") || status.startsWith("failed") ? "sell" : "neutral";
  return <Badge variant={v}>{status}</Badge>;
}

function PatternTable({ rows, showValidation = false }: { rows: ResearchPatternRow[]; showValidation?: boolean }) {
  if (!rows.length) return <div className="p-4"><EmptyState title="None" /></div>;
  return (
    <div className="overflow-x-auto">
      <Table>
        <THead>
          <TR>
            <TH>TF</TH><TH>Pattern</TH><TH>Dir</TH><TH className="text-right">Trades</TH><TH className="text-right">Win</TH>
            <TH className="text-right">Mean R</TH><TH className="text-right">Edge vs controls</TH><TH className="text-right">q</TH><TH>Status</TH>
            {showValidation && <TH>Validation</TH>}
          </TR>
        </THead>
        <TBody>
          {rows.map((r) => (
            <TR key={`${r.tf}-${r.pattern}-${r.direction}`}>
              <TD className="num">{r.tf}</TD>
              <TD className="whitespace-nowrap">{r.pattern.replaceAll("_", " ")}</TD>
              <TD><Badge variant={r.direction === "long" ? "buy" : "sell"}>{r.direction}</Badge></TD>
              <TD className="num text-right">{r.trades.toLocaleString()}</TD>
              <TD className="num text-right">{pct(r.win_rate)}</TD>
              <TD className="num text-right">{num(r.mean_r, 2, true)}</TD>
              <TD className="num text-right whitespace-nowrap">{num(r.edge, 2, true)} ± {num(r.edge_se, 2)}</TD>
              <TD className="num text-right">{r.q === null ? "–" : r.q.toFixed(3)}</TD>
              <TD><StatusBadge status={r.status} /></TD>
              {showValidation && <TD>{r.validation ? <StatusBadge status={r.validation.verdict} /> : <span className="text-muted-foreground">not run</span>}</TD>}
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function DatasetCard({ d }: { d: GoldResearch }) {
  const ds = d.dataset;
  if (!ds) return null;
  return (
    <Card>
      <CardHeader><CardTitle>Dataset <SegmentBadge>source data</SegmentBadge></CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="First traded minute" value={day(ds.first_traded_minute)} />
          <Stat label="Last minute" value={day(ds.last_minute)} />
          <Stat label="Clean M1 candles" value={ds.m1_candles?.toLocaleString() ?? "–"} sub={ds.price} />
          <Stat label="Traded coverage" value={ds.traded_coverage_pct !== null ? `${ds.traded_coverage_pct}%` : "–"} sub={`${ds.material_gaps ?? "–"} material gaps`} />
        </div>
        <div className="overflow-x-auto">
          <Table>
            <THead><TR><TH>Timeframe</TH><TH>From</TH><TH>To</TH><TH className="text-right">Candles</TH><TH>Rebuilt from M1</TH></TR></THead>
            <TBody>
              {Object.entries(ds.timeframes).map(([tf, v]) => (
                <TR key={tf}>
                  <TD className="num">{tf}</TD><TD className="num">{day(v.earliest)}</TD><TD className="num">{day(v.latest)}</TD>
                  <TD className="num text-right">{v.bars.toLocaleString()}</TD>
                  <TD>{v.identical_to_m1_rebuild === undefined || v.identical_to_m1_rebuild === null ? "–" : v.identical_to_m1_rebuild ? "identical" : "mismatch"}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
        <SourceNote>{ds.source ?? "Dukascopy"}. Filler minutes removed, never filled: {ds.filler_minutes_removed?.toLocaleString() ?? "–"}. Invalid candles: {ds.invalid_candles ?? "–"}. Duplicates: {ds.duplicates ?? "–"}.</SourceNote>
      </CardContent>
    </Card>
  );
}

function SplitCard({ d }: { d: GoldResearch }) {
  const s = d.split;
  if (!s) return null;
  return (
    <Card>
      <CardHeader><CardTitle>Chronological split</CardTitle></CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat label="Training (70%)" value={`${day(s.train.start)} → ${day(s.train.end)}`} sub="finding candidates" wrap />
        <Stat label="Validation (15%)" value={`${day(s.validation.start)} → ${day(s.validation.end)}`} sub="confirming them only" wrap />
        <Stat label="Final test (15%)" value={`${day(s.test.start)} → now`} sub="sealed: read once, at the very end" wrap />
      </CardContent>
    </Card>
  );
}

function Patterns({ d }: { d: GoldResearch }) {
  const p = d.patterns;
  const [tab, setTab] = useState<"candidates" | "best" | "worst" | "all">("candidates");
  const [tf, setTf] = useState<string>("all");
  const tfs = useMemo(() => Array.from(new Set((p?.all ?? []).map((r) => r.tf))), [p]);
  if (!p) return <Card><CardContent className="p-4"><EmptyState title="Pattern study not run yet" hint="Results appear here after the training-period discovery." /></CardContent></Card>;
  const rows = tab === "candidates" ? p.candidates : tab === "best" ? p.best : tab === "worst" ? p.worst : p.all.filter((r) => tf === "all" || r.tf === tf);
  return (
    <Card>
      <CardHeader className="flex-wrap gap-2">
        <CardTitle>Pattern discovery <SegmentBadge>training period</SegmentBadge></CardTitle>
        <Tabs tabs={[{ id: "candidates", label: `Candidates (${p.candidates.length})` }, { id: "best", label: "Best 10" }, { id: "worst", label: "Worst 10" }, { id: "all", label: `All tests (${p.tests})` }]} value={tab} onChange={setTab} />
      </CardHeader>
      <CardContent className="space-y-3 p-0">
        <div className="grid grid-cols-2 gap-4 px-4 pt-2 sm:grid-cols-4">
          <Stat label="Tests with enough trades" value={p.tests.toLocaleString()} />
          <Stat label="Candidates (BH q < 0.10)" value={p.candidates.length} />
          <Stat label="Main test" value={p.main_test ? `${p.main_test.target_r}R / ${p.main_test.hold_candles} candles` : "–"} />
          <Stat label="Discovery stages" value={p.stages} />
        </div>
        {tab === "all" && (
          <div className="flex flex-wrap gap-2 px-4">
            {["all", ...tfs].map((x) => (
              <button key={x} onClick={() => setTf(x)} className={`rounded border px-2 py-0.5 text-xs ${tf === x ? "bg-primary/10 text-primary" : "text-muted-foreground"}`}>{x}</button>
            ))}
          </div>
        )}
        <PatternTable rows={rows} showValidation={tab === "candidates"} />
        <div className="px-4 pb-4"><SourceNote>Edge = result minus matched random trades with the same entry type, stop size, session, volatility and year. Candidates are only hypotheses until validation confirms them.</SourceNote></div>
      </CardContent>
    </Card>
  );
}

function Scenarios({ d }: { d: GoldResearch }) {
  const s = d.scenarios;
  if (!s) return null;
  const cols = ["trend_regime", "vol_level", "session", "structural_regime", "range_regime"].filter((c) => typeof s[c] === "object");
  return (
    <Card>
      <CardHeader><CardTitle>Market scenarios <SegmentBadge>training period, descriptive</SegmentBadge></CardTitle></CardHeader>
      <CardContent className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {cols.map((c) => (
          <div key={c} className="overflow-x-auto">
            <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">{c.replaceAll("_", " ")}</div>
            <Table>
              <THead><TR><TH>Condition</TH><TH className="text-right">Trades</TH><TH className="text-right">Mean R</TH><TH className="text-right">Edge</TH></TR></THead>
              <TBody>
                {Object.entries(s[c] as Record<string, ScenarioCell>).map(([k, v]) => (
                  <TR key={k}><TD>{k.replaceAll("_", " ")}</TD><TD className="num text-right">{v.trades.toLocaleString()}</TD><TD className="num text-right">{num(v.mean_r, 3, true)}</TD><TD className="num text-right">{num(v.edge, 3, true)}</TD></TR>
                ))}
              </TBody>
            </Table>
          </div>
        ))}
        <div className="lg:col-span-2"><SourceNote>{s.note as string}</SourceNote></div>
      </CardContent>
    </Card>
  );
}

function Models({ d }: { d: GoldResearch }) {
  const m = d.models;
  if (!m) return <Card><CardHeader><CardTitle>Model training</CardTitle></CardHeader><CardContent><EmptyState title="Not trained yet" hint="Models are trained after the pattern study, on training data only." /></CardContent></Card>;
  return (
    <Card>
      <CardHeader><CardTitle>Model training <SegmentBadge>{m.segment}</SegmentBadge></CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="text-sm text-muted-foreground">Label: {m.label}. No model is used for live probabilities until it passes validation and calibration, and promotion needs explicit approval.</div>
        {Object.entries(m.tfs).map(([tf, r]) => (
          <div key={tf} className="overflow-x-auto">
            <div className="mb-1 text-sm font-medium">{tf}: {r.rows.toLocaleString()} rows, {r.features} features, challenger <span className="num">{r.challenger}</span> {r.champion ? `· champion ${r.champion}` : "· no champion"}{r.validation ? ` · validation ${r.validation.passed_gate ? "passed" : "did not pass"}` : " · validation not run"}</div>
            <Table>
              <THead><TR><TH>Model</TH><TH className="text-right">ROC-AUC</TH><TH className="text-right">PR-AUC</TH><TH className="text-right">Brier skill</TH><TH className="text-right">Log loss</TH><TH className="text-right">ECE</TH></TR></THead>
              <TBody>
                {Object.entries(r.comparison).map(([k, v]) => (
                  <TR key={k}><TD>{k}{k === r.best_kind ? " (best)" : ""}</TD><TD className="num text-right">{num(v.roc_auc, 3)}</TD><TD className="num text-right">{num(v.pr_auc, 3)}</TD><TD className="num text-right">{num(v.brier_skill, 4, true)}</TD><TD className="num text-right">{num(v.log_loss, 4)}</TD><TD className="num text-right">{num(v.ece, 3)}</TD></TR>
                ))}
              </TBody>
            </Table>
            <SourceNote>Shuffled-label check ROC-AUC {num(r.shuffled_label_auc, 3)} (about 0.5 means no leakage). Calibrated: Brier skill {num(r.calibrated.brier_skill, 4, true)}, ECE {num(r.calibrated.ece, 3)}.</SourceNote>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function LiveSignal() {
  const q = useSignal("XAUUSD");
  return (
    <Card>
      <CardHeader className="flex-wrap gap-2"><CardTitle>Current XAUUSD signal <SegmentBadge>live, analysis only</SegmentBadge></CardTitle><Link href="/signals" className="text-sm text-primary underline">Full analysis</Link></CardHeader>
      <CardContent>
        <QueryState query={q}>
          {(s) => (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Overall bias" value={s.overall?.label ?? "–"} sub={s.overall?.detail} wrap />
              <Stat label="Decision" value={s.analysis_report?.final_decision ?? s.report?.final_instruction ?? "NO TRADE"} wrap />
              <Stat label="Signal class" value={s.best?.signal_class?.replaceAll("_", " ") ?? "–"} />
              <Stat label="Confluence" value={s.best?.score ?? "–"} sub={s.best?.confluence_band ? `${s.best.confluence_band.replaceAll("_", " ")} (not a probability)` : undefined} />
            </div>
          )}
        </QueryState>
      </CardContent>
    </Card>
  );
}

function ExperimentCard({ e }: { e: ResearchExperiment }) {
  const rows = [...e.rows].sort((x, y) => (y.trades ?? 0) - (x.trades ?? 0));
  return (
    <Card data-testid={`experiment-${e.key}`}>
      <CardHeader className="flex-wrap gap-2">
        <CardTitle>{e.name} <SegmentBadge>{e.segment ?? "development"}</SegmentBadge></CardTitle>
        <Badge variant={e.candidates > 0 ? "buy" : "neutral"}>{e.candidates} candidates</Badge>
      </CardHeader>
      <CardContent className="space-y-3 p-0">
        <p className="px-4 text-sm text-muted-foreground">
          {e.description}. {e.tests_run ?? 0} of {e.pre_registered ?? 0} pre-registered tests had enough trades to run
          {e.trials_counted ? `; the deflated Sharpe ratio counts ${e.trials_counted.toLocaleString()} trials across all experiments` : ""}.
          Mean R is per trade after spread and financing; the edge compares each setup with random limit orders of the same shape.
        </p>
        <Table>
          <THead><TR><TH>TF</TH><TH>Setup</TH><TH>Direction</TH><TH className="text-right">Trades</TH><TH className="text-right">Mean R</TH>
            <TH className="text-right">Random R</TH><TH className="text-right">Edge</TH><TH className="text-right">q</TH><TH>Result</TH></TR></THead>
          <TBody>
            {rows.map((r) => (
              <TR key={`${r.tf}${r.setup}${r.direction}`}>
                <TD className="num">{r.tf}</TD>
                <TD className="text-xs">{r.setup.replace(/^([A-Z]\d+)_/, "$1 · ").replaceAll("_", " ")}</TD>
                <TD className="text-xs">{r.direction}</TD>
                <TD className="num text-right">{r.trades.toLocaleString()}</TD>
                <TD className={`num text-right ${(r.mean_r ?? 0) > 0 ? "text-bull" : "text-bear"}`}>{num(r.mean_r, 3, true)}</TD>
                <TD className="num text-right text-muted-foreground">{num(r.control_r, 3, true)}</TD>
                <TD className="num text-right">{num(r.edge, 3, true)}</TD>
                <TD className="num text-right">{num(r.q, 3)}</TD>
                <TD><Badge variant={r.candidate ? "buy" : "neutral"}>{r.candidate ? "candidate" : r.q === null ? "too few trades" : "not a candidate"}</Badge></TD>
              </TR>
            ))}
          </TBody>
        </Table>
        <p className="px-4 pb-4 text-xs text-muted-foreground">Full report: {e.report}. The sealed final-test period was not used.</p>
      </CardContent>
    </Card>
  );
}

export default function GoldResearchPage() {
  const q = useGoldResearch();
  return (
    <>
      <PageHeader title="Gold Research" description="23 years of Dukascopy 1-minute XAUUSD (bid and ask): data quality, the sealed chronological split, every pattern tested against matched random trades, market scenarios and model status. Historical research and backtest output only." />
      <div className="space-y-5">
        <QueryState query={q}>
          {(d) =>
            !d.available ? (
              <Card><CardContent className="p-4"><EmptyState title="Research results not available yet" hint="They appear after the historical study has run on the research machine." /></CardContent></Card>
            ) : (
              <>
                <div className="flex flex-wrap gap-2 text-xs">{Object.entries(d.status).map(([k, v]) => <Badge key={k} variant="neutral">{k.replaceAll("_", " ")}: {v}</Badge>)}</div>
                <DatasetCard d={d} />
                <SplitCard d={d} />
                <Patterns d={d} />
                <Scenarios d={d} />
                <Models d={d} />
                {(d.experiments ?? []).map((e) => <ExperimentCard key={e.key} e={e} />)}
                {d.disclaimer && <SourceNote>{d.disclaimer}</SourceNote>}
              </>
            )
          }
        </QueryState>
        <LiveSignal />
      </div>
    </>
  );
}

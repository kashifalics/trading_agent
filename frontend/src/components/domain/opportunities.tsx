"use client";

import { AlertTriangle, ChevronDown } from "lucide-react";
import { useMemo } from "react";
import { CandleChart } from "@/components/charts/candle-chart";
import { COLORS, type ChartLine, type ChartMarker, type ChartZone } from "@/components/charts/overlays";
import { CallBadge, CallCard } from "@/components/domain/call";
import { DecisionBadge, EmptyState, ErrorState } from "@/components/domain/common";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useCandles, useInstruments, useOppValidation, useOpportunity } from "@/lib/hooks";
import type {
  AnalogueEvidence,
  OppInstrument,
  OppStatus,
  OppStyleBest,
  OppSummary,
  Opportunity,
  OpportunityDetail,
  ScoreBreakdown,
  TfStatus,
  ValidationStatus,
} from "@/lib/opportunity-types";
import { cn, fmtDate, fmtNum, fmtPct, fmtPrice, timeAgo } from "@/lib/utils";

export const SCORE_LABEL = "Evidence Score — Not Win Probability";

export const STATUS_LABEL: Record<OppStatus, string> = {
  none: "No setup",
  watchlist: "Watchlist",
  waiting_for_confirmation: "Waiting for confirmation",
  entry_triggered: "Entry triggered",
  invalidated: "Invalidated",
  expired: "Expired",
};
const STATUS_VARIANT: Record<OppStatus, "buy" | "sell" | "wait" | "neutral" | "info"> = {
  none: "neutral", watchlist: "info", waiting_for_confirmation: "wait", entry_triggered: "buy", invalidated: "sell", expired: "neutral",
};
const VALIDATION: Record<ValidationStatus, { label: string; variant: "buy" | "sell" | "wait" | "neutral"; help: string }> = {
  validated: { label: "validated", variant: "buy", help: "Passed out-of-sample validation" },
  untested: { label: "Not validated", variant: "wait", help: "No out-of-sample test exists for this setup rule set" },
  no_edge: { label: "no edge found", variant: "neutral", help: "Tested out of sample: not distinguishable from zero (or too few trades)" },
  negative: { label: "negative OOS", variant: "sell", help: "Tested out of sample: the rules lose money after costs" },
};
const TF_VARIANT: Record<TfStatus, "buy" | "info" | "wait" | "sell" | "neutral"> = {
  completed: "buy", running: "info", insufficient_data: "wait", unsupported: "neutral", failed: "sell",
};
const TF_LABEL: Record<TfStatus, string> = {
  completed: "Completed", running: "Running", insufficient_data: "Insufficient data", unsupported: "Unsupported", failed: "Failed",
};
const STYLE_LABEL: Record<string, string> = { scalping: "Scalping", intraday: "Intraday", swing: "Swing", long_term: "Long-term" };
const COMPONENT_LABEL: Record<string, string> = {
  htf_alignment: "Higher-timeframe alignment", structure_quality: "Market-structure quality", price_action_confirmation: "Price-action confirmation",
  historical_analogues: "Historical analogues", momentum: "Momentum", volatility_suitability: "Volatility suitability", risk_reward: "Risk / reward",
  data_quality: "Data quality", strategy_validation: "Strategy validation",
};

export const holding = (s: number | null) => (s === null ? "—" : s >= 86400 ? `~${Math.round(s / 86400)}d` : s >= 3600 ? `~${Math.round(s / 3600)}h` : `~${Math.round(s / 60)}m`);

export function usePrecision(symbol: string): number {
  const inst = useInstruments();
  return inst.data?.find((i) => i.canonical_symbol === symbol)?.price_precision ?? 2;
}

export function ValidationBadge({ status }: { status: ValidationStatus | null }) {
  const v = VALIDATION[status ?? "untested"];
  return <Badge variant={v.variant} title={v.help}>{v.label}</Badge>;
}
export function StatusBadge({ status }: { status: OppStatus }) {
  return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>;
}

function Stat({ label, value, sub, testId }: { label: string; value: React.ReactNode; sub?: React.ReactNode; testId?: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card p-4 shadow-card" data-testid={testId}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="num mt-1 text-xl font-bold leading-tight text-foreground">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ top summary
export function SummaryBar({ s }: { s: OppSummary }) {
  const sc = s.scan;
  const sum = sc?.summary;
  const fresh = sum?.data_freshness;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="opp-summary">
      <Stat label="Latest scan" value={sc ? timeAgo(sc.finished_at) : "never"} sub={sc ? `#${sc.id} · ${sc.status.replace(/_/g, " ")} · ${sc.trigger}` : "no scan yet"} testId="stat-scan" />
      <Stat label="Data at scan time" value={fresh?.max_stale_bars == null ? "—" : fresh.max_stale_bars === 0 ? "up to date" : `${fresh.max_stale_bars} bars behind`}
        sub={sum?.latest_candle_ts ? `latest candle ${timeAgo(new Date(sum.latest_candle_ts * 1000).toISOString())} (${fmtDate(new Date(sum.latest_candle_ts * 1000).toISOString())})` : "worst timeframe"} testId="stat-fresh" />
      <Stat label="Instruments scanned" value={sum ? `${sum.instruments_scanned} / ${sum.instruments_requested}` : "—"}
        sub={sum?.instruments_unavailable.length ? `unavailable: ${sum.instruments_unavailable.join(", ")}` : "all available"} testId="stat-instruments" />
      <Stat label="Timeframes completed" value={sum ? `${sum.timeframes_completed} / ${sum.timeframes_total}` : "—"} sub="of 14 per instrument" testId="stat-tfs" />
      <Stat label="Opportunities found" value={sum ? sum.opportunities_actionable : "—"} sub={sum ? `${sum.opportunities_watchlist} on watchlist · ${sum.wait} WAIT` : undefined} testId="stat-found" />
      <Stat label="Next scan" value={s.running_scan ? "running…" : s.next_scan.enabled ? (s.next_scan.next_run_estimate ? timeAgo(s.next_scan.next_run_estimate).replace("ago", "") || "soon" : "scheduled") : "manual"}
        sub={s.next_scan.enabled ? `every ${s.next_scan.interval_minutes} min` : "automatic scanning off"} testId="stat-next" />
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ style cards
export function StyleCard({ item, onSelect, precision }: { item: OppStyleBest; onSelect: (id: number) => void; precision: (s: string) => number }) {
  const o = item.best ?? item.fallback_wait;
  const lv = o?.call?.levels ?? o?.call?.hypothetical ?? null;
  return (
    <Card data-testid={`style-${item.style}`} className="flex flex-col">
      <CardHeader>
        <CardTitle>Best {STYLE_LABEL[item.style]} Opportunity</CardTitle>
        <span className="num text-xs text-muted-foreground">{item.setup_timeframes.join(" · ")}</span>
      </CardHeader>
      <CardContent className="flex-1 space-y-2 text-sm">
        {!o ? (
          <p className="text-muted-foreground">No scan result for this style yet.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              {o.call ? <CallBadge call={o.call} className="text-[10px]" /> : <DecisionBadge decision={o.direction} />}
              <span className="font-medium">{o.symbol}</span>
              {o.setup_timeframe && <span className="num text-muted-foreground">{o.setup_timeframe}</span>}
              <StatusBadge status={o.status} />
              {o.status !== "none" && <ValidationBadge status={o.validation_status} />}
            </div>
            {lv ? (
              <div className="num grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
                {o.call?.hypothetical && <span className="col-span-2 font-sans font-semibold text-warn">HYPOTHETICAL — UNVALIDATED</span>}
                <span className="text-muted-foreground">Entry</span><span>{lv.entry_zone ? `${fmtPrice(lv.entry_zone[0], precision(o.symbol))} – ${fmtPrice(lv.entry_zone[1], precision(o.symbol))}` : fmtPrice(lv.entry, precision(o.symbol))}</span>
                <span className="text-muted-foreground">Stop</span><span className="text-bear">{fmtPrice(lv.stop_loss, precision(o.symbol))}</span>
                <span className="text-muted-foreground">TP1</span><span className="text-bull">{fmtPrice(lv.targets[0]?.price, precision(o.symbol))}</span>
                <span className="text-muted-foreground">R/R</span><span>{lv.risk_reward == null ? "—" : `${fmtNum(lv.risk_reward, 2)}R`}</span>
                <span className="text-muted-foreground">Holding</span><span>{holding(o.expected_holding_seconds)}</span>
              </div>
            ) : (
              <div className="space-y-1 text-xs text-muted-foreground">
                <p className="text-foreground">{o.call?.headline ?? (o.side ? `Leaning ${o.side}, not actionable` : "No actionable setup")}</p>
                {o.call?.next_condition ? <p>Next: {o.call.next_condition}</p> : o.wait_reasons.slice(0, 2).map((r, i) => <p key={i}>• {r}</p>)}
              </div>
            )}
            {o.evidence_score !== null && (
              <div className="text-xs">
                <span className="num text-base font-semibold">{fmtNum(o.evidence_score, 0)}</span>
                <span className="ml-1 text-muted-foreground">/ 100 · {SCORE_LABEL}</span>
              </div>
            )}
          </>
        )}
      </CardContent>
      {o && (
        <div className="border-t p-2">
          <button className="w-full rounded px-2 py-1 text-left text-xs text-primary hover:bg-muted" onClick={() => onSelect(o.id)}>View evidence →</button>
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------------------------------------ instruments / timeframes
export function InstrumentStatus({ items }: { items: OppInstrument[] }) {
  return (
    <div className="space-y-2" data-testid="instrument-status">
      {items.map((i) => (
        <details key={i.symbol} className="rounded-xl border border-border/60 bg-card" open={i.status !== "scanned" ? true : undefined}>
          <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-3 py-2 text-sm">
            <span className="font-medium">{i.symbol}</span>
            <Badge variant={i.status === "scanned" ? "buy" : i.status === "failed" ? "sell" : "wait"}>{i.status === "scanned" ? "scanned" : i.status}</Badge>
            {i.provider && <span className="text-xs text-muted-foreground">source: {i.provider}{i.provider_status && i.provider_status !== "active" ? ` (${i.provider_status})` : ""}</span>}
            {i.timeframes && <span className="num text-xs text-muted-foreground">{i.timeframes.filter((t) => t.status === "completed").length}/14 timeframes</span>}
            {i.reason && <span className="text-xs text-muted-foreground">— {i.reason}</span>}
          </summary>
          {i.timeframes && (
            <div className="grid grid-cols-2 gap-2 border-t p-3 sm:grid-cols-4 lg:grid-cols-7">
              {i.timeframes.map((t) => (
                <div key={t.timeframe} className="rounded border p-2 text-xs" title={t.reason ?? ""}>
                  <div className="flex items-center justify-between"><span className="num font-medium">{t.timeframe}</span><Badge variant={TF_VARIANT[t.status]}>{TF_LABEL[t.status]}</Badge></div>
                  <div className="num mt-1 text-muted-foreground">{t.n_bars} bars{t.derived_from ? ` · from ${t.derived_from}` : ""}{t.stale_bars ? ` · ${t.stale_bars} behind` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </details>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ market read by timeframe
const ALL_TFS = ["1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M", "3M", "6M", "12M"];

/** One row per scanned instrument, one cell per timeframe: structure trend and premium/discount. Shows the market's state even when no setup qualifies. */
export function TimeframeMatrix({ items }: { items: OppInstrument[] }) {
  const scanned = items.filter((i) => i.status === "scanned" && i.timeframes);
  if (!scanned.length) return null;
  return (
    <div className="overflow-x-auto" data-testid="tf-matrix">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
            <th className="px-2 py-2">Instrument</th>
            {ALL_TFS.map((t) => <th key={t} className="px-1.5 py-2 text-center normal-case">{t}</th>)}
          </tr>
        </thead>
        <tbody>
          {scanned.map((i) => (
            <tr key={i.symbol} className="border-t border-border/60">
              <td className="px-2 py-2 font-medium">{i.symbol}</td>
              {ALL_TFS.map((code) => {
                const t = i.timeframes?.find((x) => x.timeframe === code);
                const v = t?.view;
                if (!t || !v) {
                  return <td key={code} className="px-1.5 py-2 text-center text-muted-foreground" title={t?.reason ?? "no data"} data-cell="na">–</td>;
                }
                const dir = v.trend || v.bias;
                const zone = v.zone === "premium" ? "P" : v.zone === "discount" ? "D" : v.zone === "equilibrium" ? "E" : "";
                return (
                  <td key={code} className="px-1.5 py-2 text-center" title={`${t.timeframe}: ${v.summary}${t.stale_bars ? ` · ${t.stale_bars} bars behind` : ""}`} data-cell={dir > 0 ? "up" : dir < 0 ? "down" : "flat"}>
                    <span className={dir > 0 ? "text-bull" : dir < 0 ? "text-bear" : "text-muted-foreground"}>{dir > 0 ? "▲" : dir < 0 ? "▼" : "▬"}</span>
                    {zone && <span className="ml-0.5 text-[10px] text-muted-foreground">{zone}</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted-foreground">▲ bullish / ▼ bearish market structure, ▬ undetermined · P premium, D discount, E equilibrium of the latest swing range · – no usable data. Hover a cell for the detail. This is a description of the market, not a signal.</p>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ consolidated table
export function OpportunityTable({ rows, selected, onSelect, precision }: { rows: Opportunity[]; selected: number | null; onSelect: (id: number) => void; precision: (s: string) => number }) {
  if (!rows.length) return <EmptyState title="No opportunities yet" hint="Run a scan to analyse every supported instrument across all timeframes." />;
  return (
    <Table data-testid="opp-table">
      <THead>
        <TR>
          <TH>Rank</TH><TH>Instrument</TH><TH>Style</TH><TH>Decision</TH><TH className="text-right">Entry</TH><TH className="text-right">Stop Loss</TH>
          <TH className="text-right">TP1</TH><TH className="text-right">TP2</TH><TH className="text-right">TP3</TH><TH className="text-right">R/R</TH>
          <TH className="text-right" title={SCORE_LABEL}>Evidence Score</TH><TH>Setup status</TH><TH>Last updated</TH>
        </TR>
      </THead>
      <TBody>
        {rows.map((o) => {
          const p = precision(o.symbol);
          const lv = o.call?.levels ?? o.call?.hypothetical ?? null; // ENTER levels, or hypothetical ones in experimental mode
          const ref = !o.call?.levels; // hypothetical levels are greyed
          return (
            <TR key={o.id} className={cn("cursor-pointer", selected === o.id && "bg-muted/60", o.rank === null && "bg-muted/30")} onClick={() => onSelect(o.id)} data-testid={`opp-row-${o.id}`}>
              <TD className="num">{o.rank ?? "—"}{o.correlated_with_rank ? <span className="ml-1 text-xs text-muted-foreground" title="Same instrument and direction as a higher-ranked setup: one exposure, not an independent idea">≈#{o.correlated_with_rank}</span> : null}</TD>
              <TD className="font-medium">{o.symbol}</TD>
              <TD>{STYLE_LABEL[o.style]}{o.setup_timeframe ? <span className="num ml-1 text-xs text-muted-foreground">{o.setup_timeframe}</span> : null}</TD>
              <TD>
                {o.call ? <CallBadge call={o.call} className="text-[10px]" /> : <DecisionBadge decision={o.direction} />}
                {o.side ? <span className="ml-1 text-xs text-muted-foreground">{o.side}</span> : null}
              </TD>
              <TD className={cn("num text-right", ref && "text-muted-foreground")}>{!lv ? "—" : lv.entry_zone ? `${fmtPrice(lv.entry_zone[0], p)} – ${fmtPrice(lv.entry_zone[1], p)}` : fmtPrice(lv.entry, p)}</TD>
              <TD className={cn("num text-right", ref ? "text-muted-foreground" : "text-bear")}>{lv ? fmtPrice(lv.stop_loss, p) : "—"}</TD>
              {[0, 1, 2].map((k) => <TD key={k} className={cn("num text-right", ref ? "text-muted-foreground" : "text-bull")}>{lv?.targets[k] ? fmtPrice(lv.targets[k].price, p) : "—"}</TD>)}
              <TD className="num text-right">{lv?.risk_reward == null ? "—" : `${fmtNum(lv.risk_reward, 2)}R`}</TD>
              <TD className="num text-right">{o.evidence_score == null ? "—" : fmtNum(o.evidence_score, 0)} {o.status !== "none" && <ValidationBadge status={o.validation_status} />}</TD>
              <TD><StatusBadge status={o.status} /></TD>
              <TD className="whitespace-nowrap text-xs text-muted-foreground">{timeAgo(o.last_seen_at)}</TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}

// ------------------------------------------------------------------------------------------------ detail view
function Section({ title, children, open = false, testId }: { title: string; children: React.ReactNode; open?: boolean; testId?: string }) {
  return (
    <details open={open} className="group rounded-xl border border-border/60 bg-card" data-testid={testId}>
      <summary className="flex cursor-pointer items-center justify-between px-3 py-2 text-sm font-medium">
        {title}<ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="space-y-2 border-t p-3 text-sm">{children}</div>
    </details>
  );
}
const Bullets = ({ items, empty }: { items: string[]; empty: string }) =>
  items.length ? <ul className="list-disc space-y-1 pl-5">{items.map((t, i) => <li key={i}>{t}</li>)}</ul> : <p className="text-muted-foreground">{empty}</p>;

export function ScorePanel({ score }: { score: ScoreBreakdown | null }) {
  if (!score) return <p className="text-muted-foreground">No score: no candidate setup exists, so there is nothing to score.</p>;
  return (
    <div data-testid="score-panel" className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="num text-3xl font-semibold">{fmtNum(score.score, 0)}</span><span className="text-muted-foreground">/ 100</span>
        <Badge variant="wait">{SCORE_LABEL}</Badge>
        {score.cap.applied && <Badge variant="sell" title={score.cap.reason ?? ""}>capped from {fmtNum(score.uncapped_score, 0)}</Badge>}
      </div>
      <p className="text-xs text-muted-foreground">{score.note}</p>
      <Table>
        <THead><TR><TH>Component</TH><TH className="text-right">Weight</TH><TH className="text-right">Score</TH><TH className="text-right">Points</TH><TH>Why</TH></TR></THead>
        <TBody>
          {score.components.map((c) => (
            <TR key={c.name}><TD>{COMPONENT_LABEL[c.name] ?? c.name}</TD><TD className="num text-right">{fmtPct(c.weight)}</TD><TD className="num text-right">{fmtPct(c.raw)}</TD>
              <TD className="num text-right">{fmtNum(c.points, 1)}</TD><TD className="text-xs text-muted-foreground">{c.detail}</TD></TR>
          ))}
          {score.penalties.map((p) => (
            <TR key={p.name} className="text-bear"><TD>Penalty: {p.name.replace(/_/g, " ")}</TD><TD /><TD /><TD className="num text-right">{fmtNum(p.points, 1)}</TD><TD className="text-xs">{p.detail}</TD></TR>
          ))}
        </TBody>
      </Table>
      {score.cap.applied && <p className="text-xs text-bear">{score.cap.reason}</p>}
    </div>
  );
}

export function AnalogueTable({ a }: { a: AnalogueEvidence }) {
  if (!a.available) return <p className="text-muted-foreground">No analogue evidence: {a.reason ?? "not computed"}.</p>;
  const hs = (a.horizons ?? []).map(String);
  return (
    <div className="space-y-2" data-testid="analogues">
      <p>
        <span className="num font-semibold">{a.n_obs}</span> nearest historical situations ({a.sample_quality} sample). Hit the {a.tp_atr} ATR target before the {a.sl_atr} ATR stop in{" "}
        <span className="num font-semibold">{fmtPct(a.tp_first?.frequency ?? null)}</span> of them (95% CI {fmtPct(a.tp_first?.ci_low ?? null)}–{fmtPct(a.tp_first?.ci_high ?? null)}),
        versus a base rate of <span className="num">{fmtPct(a.base_rate?.frequency ?? null)}</span> for all comparable bars.{a.edge_within_noise ? " The difference is within sampling noise." : ""}
      </p>
      <p className="rounded border border-warn/30 bg-warn/5 p-2 text-xs text-warn">
        This is a historical frequency of similar situations, not the probability that this trade will succeed. A small or clustered sample is not statistical proof.
      </p>
      <div className="num grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        {hs.map((h) => <div key={h} className="rounded border p-2"><div className="text-muted-foreground">Mean fwd return, {h} bars</div><div>{fmtNum(a.forward_return_atr?.[h]?.mean, 2)} ATR</div></div>)}
        <div className="rounded border p-2"><div className="text-muted-foreground">Mean MFE</div><div>{fmtNum(a.mfe_atr?.mean, 2)} ATR</div></div>
        <div className="rounded border p-2"><div className="text-muted-foreground">Mean MAE</div><div>{fmtNum(a.mae_atr?.mean, 2)} ATR</div></div>
      </div>
      <Table>
        <THead><TR><TH>Date</TH><TH>Instrument · TF</TH><TH className="text-right">Similarity</TH>{hs.map((h) => <TH key={h} className="text-right">Fwd {h}b (ATR)</TH>)}<TH className="text-right">MFE</TH><TH className="text-right">MAE</TH><TH>Outcome</TH></TR></THead>
        <TBody>
          {(a.neighbors ?? []).map((n) => (
            <TR key={n.ts}><TD className="num whitespace-nowrap">{fmtDate(new Date(n.ts * 1000).toISOString())}</TD><TD>{a.neighbors ? n.timeframe : ""}</TD>
              <TD className="num text-right">{fmtNum(n.similarity, 2)}</TD>
              {hs.map((h) => <TD key={h} className="num text-right">{fmtNum(n.forward_return_atr[h], 2)}</TD>)}
              <TD className="num text-right">{fmtNum(n.mfe_atr, 2)}</TD><TD className="num text-right">{fmtNum(n.mae_atr, 2)}</TD>
              <TD><Badge variant={n.outcome === "tp_first" ? "buy" : n.outcome === "sl_first" ? "sell" : "neutral"}>{n.outcome.replace("_", " ")}</Badge></TD></TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function OpportunityChart({ d, showLevels }: { d: OpportunityDetail; showLevels: boolean }) {
  const tf = d.setup_timeframe ?? d.evidence.chart?.timeframe ?? "1H";
  const q = useCandles(d.symbol, tf, 400, !!d.setup_timeframe);
  const p = usePrecision(d.symbol);
  const { lines, zones, markers } = useMemo(() => {
    const ch = d.evidence.chart;
    const lines: ChartLine[] = [];
    const setup = showLevels ? d.evidence.setup : null;
    if (setup) {
      lines.push({ price: setup.entry_ref, color: COLORS.primary, title: `${setup.direction} entry`, dashed: true });
      lines.push({ price: setup.stop_loss, color: COLORS.bear, title: "SL" });
      setup.targets.forEach((t) => lines.push({ price: t.price, color: COLORS.bull, title: t.label, dashed: true }));
      lines.push({ price: setup.invalidation, color: COLORS.warn, title: "Invalidation", dashed: true });
    }
    const zones: ChartZone[] = [];
    for (const z of ch?.zones ?? []) zones.push({ from: z.from, low: z.low, high: z.high, color: z.direction === "bullish" ? "rgba(63,185,127,0.13)" : "rgba(239,91,100,0.13)", label: z.kind.replace(/_/g, " ") });
    for (const l of ch?.levels ?? []) zones.push({ from: l.from ?? 0, low: l.low, high: l.high, color: "rgba(138,148,166,0.16)", label: `${l.kind}${l.touches ? ` ×${l.touches}` : ""}` });
    if (setup) zones.push({ from: setup.poi.ts, low: setup.entry_low, high: setup.entry_high, color: "rgba(79,155,247,0.22)", label: "entry zone" });
    const times = new Set((q.data?.candles ?? []).map((c) => c.time));
    const markers: ChartMarker[] = [];
    for (const m of ch?.markers ?? []) if (times.has(m.ts)) markers.push({ time: m.ts, position: m.direction === "bullish" ? "belowBar" : "aboveBar", shape: m.direction === "bullish" ? "arrowUp" : "arrowDown", color: m.direction === "bullish" ? COLORS.bull : COLORS.bear, text: m.kind.replace("liquidity_", "").toUpperCase() });
    for (const m of ch?.analogue_markers ?? []) if (times.has(m.ts)) markers.push({ time: m.ts, position: "inBar", shape: "circle", color: m.outcome === "tp_first" ? COLORS.bull : m.outcome === "sl_first" ? COLORS.bear : COLORS.neutral, text: "" });
    markers.sort((a, b) => a.time - b.time);
    return { lines, zones, markers };
  }, [d, q.data, showLevels]);
  if (!d.setup_timeframe) return null;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (q.isLoading || !q.data) return <Skeleton className="h-[420px] w-full" />;
  if (!q.data.candles.length) return <EmptyState title="No stored candles for this chart" hint="Sync this timeframe to see the setup drawn." />;
  return (
    <div data-testid="opp-chart">
      <CandleChart candles={q.data.candles} precision={p} lines={lines} zones={zones} markers={markers} height={420} resetKey={`${d.id}-${tf}`} />
      <p className="mt-1 text-xs text-muted-foreground">{d.symbol} {tf} · green/red circles = historical analogues that hit target/stop first{showLevels ? " · blue band = entry zone" : ""} · grey bands = support/resistance</p>
    </div>
  );
}

export function OpportunityDetailView({ id }: { id: number }) {
  const q = useOpportunity(id);
  const p = usePrecision(q.data?.symbol ?? "");
  if (q.isLoading) return <Skeleton className="h-64 w-full" />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data, ev = d.evidence, s = ev.setup;
  const hypo = !d.call?.levels && !!d.call?.hypothetical;
  const showLevels = !!s && !!(d.call?.levels || d.call?.hypothetical);
  return (
    <Card data-testid="opp-detail">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          {d.call ? <CallBadge call={d.call} /> : <DecisionBadge decision={d.direction} />} {d.symbol} · {STYLE_LABEL[d.style]}{d.setup_timeframe ? ` · ${d.setup_timeframe}` : ""} <StatusBadge status={d.status} /> <ValidationBadge status={d.validation_status} />
        </CardTitle>
        <span className="text-xs text-muted-foreground">{d.provider} · {ev.scope}</span>
      </CardHeader>
      <CardContent className="space-y-3">
        {d.call && <CallCard call={d.call} symbol={d.symbol} precision={p} title={`Decision · ${STYLE_LABEL[d.style]}`} />}
        {ev.note && <p className="rounded border border-warn/30 bg-warn/5 p-2 text-xs text-warn" role="note">{ev.note}</p>}
        {ev.validation.status !== "validated" && (
          <p className="flex items-start gap-2 rounded border border-warn/30 bg-warn/5 p-2 text-xs text-warn" role="note">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden /> {ev.validation.summary}
          </p>
        )}
        {s && showLevels && (
          <div className="num grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:grid-cols-8" data-testid="levels">
            {hypo && <p className="col-span-full font-sans text-xs font-semibold text-warn">HYPOTHETICAL — UNVALIDATED levels (experimental analysis mode)</p>}
            <Stat label="Entry zone" value={`${fmtPrice(s.entry_low, p)} – ${fmtPrice(s.entry_high, p)}`} />
            <Stat label="Stop loss" value={<span className="text-bear">{fmtPrice(s.stop_loss, p)}</span>} />
            {s.targets.map((t) => <Stat key={t.label} label={`${t.label} · ${fmtNum(t.rr, 2)}R`} value={<span className="text-bull">{fmtPrice(t.price, p)}</span>} />)}
            <Stat label="Invalidation" value={fmtPrice(s.invalidation, p)} />
            <Stat label="Holding" value={holding(d.expected_holding_seconds)} sub="time-stop horizon, not a forecast" />
            <Stat label="Costs" value={`${fmtNum(s.cost_r, 2)}R`} sub="round trip" />
          </div>
        )}
        <OpportunityChart d={d} showLevels={showLevels} />
        {ev.score && <div className="rounded border p-3"><ScorePanel score={ev.score} /></div>}
        {!d.call?.levels && ev.wait_reasons.length > 0 && (
          <Section title="Why WAIT / what confirmation is missing" open testId="sec-wait"><Bullets items={ev.wait_reasons} empty="" /></Section>
        )}
        <Section title="Trade thesis" open testId="sec-thesis"><p>{ev.thesis ?? "No timeframe for this style has enough usable data."}</p><p className="text-xs text-muted-foreground">Scope: {ev.scope}</p></Section>
        <Section title="Multi-timeframe analysis" testId="sec-mtf">
          <Table>
            <THead><TR><TH>TF</TH><TH>Role</TH><TH>Status</TH><TH>Structure</TH><TH>Contribution</TH></TR></THead>
            <TBody>
              {ev.multi_timeframe.map((m) => (
                <TR key={m.timeframe} className={m.relevant_to_style || m.role !== "context" ? "" : "opacity-60"}>
                  <TD className="num font-medium">{m.timeframe}</TD><TD>{m.role}</TD>
                  <TD><Badge variant={TF_VARIANT[m.status]}>{TF_LABEL[m.status]}</Badge></TD>
                  <TD className="text-xs">{m.summary ?? m.reason ?? "—"}{m.derived_from ? ` (built from ${m.derived_from})` : ""}</TD>
                  <TD>{m.stance ? <Badge variant={m.stance === "supports" ? "buy" : m.stance === "opposes" ? "sell" : "neutral"}>{m.stance}</Badge> : "—"}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Section>
        {ev.structure && (
          <Section title="Market structure" testId="sec-structure">
            <p>{ev.structure.summary}</p>
            <Bullets items={ev.structure.notable_events.map((e) => `${e.kind.replace(/_/g, " ")} ${e.direction}${e.price ? ` at ${fmtPrice(e.price, p)}` : ""}: ${e.evidence}`)} empty="No recent structure events." />
            <Bullets items={[...ev.structure.live_zones.map((z) => `${z.kind.replace(/_/g, " ")} ${z.direction} ${fmtPrice(z.low, p)} – ${fmtPrice(z.high, p)}${z.dist_atr != null ? ` (${fmtNum(z.dist_atr, 1)} ATR away)` : ""}`),
              ...ev.structure.levels.map((l) => `${l.kind} band ${fmtPrice(l.low, p)} – ${fmtPrice(l.high, p)}: ${l.evidence}`)]} empty="No live zones or levels." />
          </Section>
        )}
        <Section title="Candlestick evidence" testId="sec-candles">
          {ev.candlesticks?.length ? ev.candlesticks.map((c) => (
            <p key={`${c.ts}${c.kind}`}><Badge variant={c.direction === "bullish" ? "buy" : "sell"}>{c.kind.replace(/_/g, " ")}</Badge>{" "}
              <span className="num text-xs text-muted-foreground">{fmtDate(c.time)} O {fmtPrice(c.candle.o, p)} H {fmtPrice(c.candle.h, p)} L {fmtPrice(c.candle.l, p)} C {fmtPrice(c.candle.c, p)}</span>{" "}
              {c.role === "confirmation" && <Badge variant="info">confirmation</Badge>} — {c.evidence}</p>
          )) : <p className="text-muted-foreground">No directional candlestick pattern in the last 6 bars.</p>}
        </Section>
        <Section title="Historical pattern evidence" testId="sec-analogues"><AnalogueTable a={ev.analogues} /></Section>
        {s && showLevels && (
          <>
            <Section title="Entry reasoning" testId="sec-entry"><p>{s.reasoning.entry}</p>
              <p className="font-medium">Conditions required before entry</p><Bullets items={s.conditions} empty="All entry conditions are currently met." />
              {s.confirmations.length > 0 && <><p className="font-medium">Confirmations seen</p><Bullets items={s.confirmations.map((c) => `${c.type.replace(/_/g, " ")} (${c.kind.replace(/_/g, " ")}) ${fmtDate(c.time)}: ${c.evidence}`)} empty="" /></>}
            </Section>
            <Section title="Stop-loss reasoning" testId="sec-stop"><p>{s.reasoning.stop}</p></Section>
            <Section title="Take-profit reasoning" testId="sec-tp"><Bullets items={s.reasoning.targets} empty="" /></Section>
          </>
        )}
        <Section title="Risks and opposing evidence" open testId="sec-risks">
          <p className="font-medium">{s ? `Evidence against this ${s.direction}` : "Opposing evidence"}</p>
          <Bullets items={ev.risks?.opposing_evidence ?? []} empty="No opposing structure, candle or timeframe found." />
          <p className="font-medium">Warnings</p>
          <Bullets items={ev.risks?.warnings ?? []} empty="None." />
        </Section>
        <Section title="What would invalidate the setup?" testId="sec-invalid">
          {s && showLevels ? <Bullets items={[`A candle closing ${s.direction === "BUY" ? "below" : "above"} ${fmtPrice(s.invalidation, p)} on the ${d.setup_timeframe} chart.`,
            `The first target ${fmtPrice(s.targets[0]?.price, p)} being reached before entry (the move has played out).`, `No valid trigger within ${d.style_profile.min_rr ? "the setup lifetime" : ""} (expires ${fmtDate(d.expires_at)}).`]} empty="" /> : <p className="text-muted-foreground">{d.call?.invalidation ?? "No setup to invalidate."}</p>}
        </Section>
        <Section title="Status history" testId="sec-history"><Bullets items={d.status_history.map((h) => `${fmtDate(h.at)} → ${STATUS_LABEL[h.status as OppStatus] ?? h.status}${h.note && "reason" in h.note ? `: ${String(h.note.reason)}` : ""}`)} empty="" /></Section>
      </CardContent>
    </Card>
  );
}

export function ValidationPanel() {
  const q = useOppValidation();
  if (q.isLoading) return <Skeleton className="h-24 w-full" />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const { results, reference_backtests: refs } = q.data;
  return (
    <div className="space-y-4" data-testid="validation-panel">
      <p className="text-xs text-muted-foreground">
        Walk-forward replay of the setup rules with costs. The first 60% of each history is development (not used for decisions); status comes from the last 40% only.
        Validated needs ≥ 100 out-of-sample trades, a bootstrap CI above zero and better-than-random results. Nothing here was tuned to look better.
      </p>
      {results.length === 0 ? (
        <EmptyState title="No validation experiments shipped" hint="Every setup rule set is therefore reported as not validated." />
      ) : (
        <Table>
          <THead><TR><TH>Instrument</TH><TH>Style</TH><TH>TF</TH><TH className="text-right">OOS trades</TH><TH className="text-right">OOS net E[R]</TH><TH className="text-right">Gross E[R]</TH><TH className="text-right">OOS win</TH><TH className="text-right">OOS PF</TH><TH>Status</TH></TR></THead>
          <TBody>
            {results.map((r) => (
              <TR key={`${r.symbol}${r.style}${r.timeframe}`} title={r.summary}>
                <TD className="font-medium">{r.symbol}</TD><TD>{STYLE_LABEL[r.style]}</TD><TD className="num">{r.timeframe}</TD>
                <TD className="num text-right">{r.oos.n_trades ?? 0}</TD><TD className="num text-right">{fmtNum(r.oos.expectancy_r, 3)}</TD>
                <TD className="num text-right">{fmtNum(r.oos_gross_zero_cost?.expectancy_r, 3)}</TD><TD className="num text-right">{fmtPct(r.oos.win_rate ?? null)}</TD>
                <TD className="num text-right">{fmtNum(r.oos.profit_factor, 2)}</TD><TD><ValidationBadge status={r.status} /></TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      {refs.length > 0 && (
        <div>
          <p className="mb-1 text-sm font-medium">Your existing backtests (shown exactly as stored)</p>
          <Table>
            <THead><TR><TH>#</TH><TH>Instrument</TH><TH>TF</TH><TH>Strategy</TH><TH className="text-right">Trades</TH><TH className="text-right">Return</TH><TH className="text-right">Profit factor</TH><TH className="text-right">Max DD</TH></TR></THead>
            <TBody>
              {refs.map((b) => (
                <TR key={b.id}><TD className="num">{b.id}</TD><TD>{b.symbol}</TD><TD className="num">{b.timeframe}</TD><TD>{b.strategy}</TD>
                  <TD className="num text-right">{b.metrics.n_trades ?? "—"}</TD><TD className="num text-right">{fmtNum(b.metrics.total_return_pct, 1)}%</TD>
                  <TD className="num text-right">{fmtNum(b.metrics.profit_factor, 2)}</TD><TD className="num text-right">{fmtNum(b.metrics.max_drawdown_pct, 1)}%</TD></TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}
    </div>
  );
}

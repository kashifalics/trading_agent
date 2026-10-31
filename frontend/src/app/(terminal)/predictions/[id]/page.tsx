"use client";

import Link from "next/link";
import { use } from "react";
import { DecisionBadge, EmptyState, PageHeader, QueryState } from "@/components/domain/common";
import { AnalysisOnlyNotice, ConfidencePanelView, EvidenceList, PlanCard, SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Stat } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useAnalogues, usePrediction } from "@/lib/hooks";
import type { Freq } from "@/lib/types";
import { fmtDate, fmtNum, fmtPct, signClass } from "@/lib/utils";

const freq = (f: Freq) => `${fmtPct(f.frequency)} (${fmtPct(f.ci_low)}–${fmtPct(f.ci_high)}, n=${f.n})`;

export default function PredictionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const pid = Number(id);
  const q = usePrediction(pid);
  const analogues = useAnalogues(q.data?.analysis_id ?? null);

  return (
    <QueryState query={q}>
      {(p) => {
        const stats = analogues.data?.summary?.stats;
        const plan = p.entry_low !== null && p.stop_loss !== null && p.take_profit?.length
          ? { direction: p.decision as "BUY" | "SELL", entry_low: p.entry_low, entry_high: p.entry_high ?? p.entry_low, entry_ref: p.entry_high ?? p.entry_low, stop_loss: p.stop_loss, invalidation: p.invalidation_level ?? p.stop_loss, targets: p.take_profit, risk_reward: p.risk_reward ?? 0, target_basis: "stored", warnings: [] }
          : null;
        return (
          <>
            <PageHeader
              title={`Prediction #${p.id} · ${p.symbol} ${p.timeframe}`}
              description={`Analysis as of ${fmtDate(p.as_of_ts)} using ${p.provider_code ?? "unknown provider"} candles.`}
              actions={<><DecisionBadge decision={p.decision} className="text-base" /><Link href="/predictions" className="text-xs text-primary hover:underline">All predictions</Link></>}
            />
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
              <div className="min-w-0 space-y-4">
                <SectionCard title="Trade plan"><PlanCard decision={p.decision} plan={plan} waitReasons={p.wait_reasons} /></SectionCard>
                <SectionCard title="Explanation">
                  <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-muted-foreground">{p.explanation}</pre>
                </SectionCard>
                <SectionCard title="Confidence — five separate views">
                  {p.confidence ? <ConfidencePanelView panel={p.confidence} /> : <EmptyState title="Confidence breakdown unavailable" />}
                </SectionCard>
                <SectionCard title="Evidence breakdown"><EvidenceList evidence={p.evidence} /></SectionCard>
                <SectionCard title="Historical analogues">
                  <QueryState query={analogues} isEmpty={(d) => !d.summary}>
                    {(a) => (
                      <div className="space-y-4">
                        <p className="text-xs text-muted-foreground">{a.note}</p>
                        {a.summary?.reason && <p className="text-sm text-warn">{a.summary.reason}</p>}
                        {stats && (
                          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                            <Stat label="Long TP first" value={freq(stats.long_tp_before_sl)} sub={`base ${fmtPct(stats.base_rate_long.frequency)}`} />
                            <Stat label="Short TP first" value={freq(stats.short_tp_before_sl)} sub={`base ${fmtPct(stats.base_rate_short.frequency)}`} />
                            <Stat label="Neither / ambiguous" value={fmtPct(stats.timeout_or_ambiguous.frequency)} />
                            <Stat label={`Fwd return (${stats.horizon_bars} bars, ATR)`} value={stats.forward_return.mean_ci ? `${fmtNum(stats.forward_return.mean_ci.mean, 2)} [${fmtNum(stats.forward_return.mean_ci.ci_low, 2)}, ${fmtNum(stats.forward_return.mean_ci.ci_high, 2)}]` : "—"} />
                            <Stat label="Mean MFE / MAE (ATR)" value={`${fmtNum(stats.excursions.mfe_mean, 2)} / ${fmtNum(stats.excursions.mae_mean, 2)}`} />
                            <Stat label="Barrier" value={`TP ${stats.tp_atr} ATR · SL ${stats.sl_atr} ATR`} />
                          </div>
                        )}
                        <Table>
                          <THead><TR><TH>#</TH><TH>When</TH><TH className="text-right">Similarity</TH><TH className="text-right">Fwd ret (ATR)</TH><TH className="text-right">MFE</TH><TH className="text-right">MAE</TH><TH>Long / Short TP first</TH></TR></THead>
                          <TBody>
                            {a.analogues.slice(0, 15).map((r) => (
                              <TR key={r.rank}>
                                <TD>{r.rank}</TD><TD className="num">{fmtDate(r.time)}</TD>
                                <TD className="num text-right">{fmtNum(r.similarity, 3)}</TD>
                                <TD className={`num text-right ${signClass(r.forward_return_atr)}`}>{fmtNum(r.forward_return_atr, 2)}</TD>
                                <TD className="num text-right">{fmtNum(r.mfe_atr, 2)}</TD><TD className="num text-right">{fmtNum(r.mae_atr, 2)}</TD>
                                <TD>{r.long_tp_before_sl ? "long ✓" : "—"} / {r.short_tp_before_sl ? "short ✓" : "—"}</TD>
                              </TR>
                            ))}
                          </TBody>
                        </Table>
                      </div>
                    )}
                  </QueryState>
                </SectionCard>
              </div>

              <aside className="space-y-4">
                <SectionCard title="Summary">
                  <div className="grid grid-cols-2 gap-3">
                    <Stat label="Confluence" value={<span className={signClass(p.confluence_score)}>{fmtNum(p.confluence_score, 2)}</span>} />
                    <Stat label="Data quality" value={fmtNum(p.data_quality_score, 2)} />
                    <Stat label="Risk / reward" value={p.risk_reward ? `1 : ${fmtNum(p.risk_reward, 2)}` : "—"} />
                    <Stat label="Model version" value={p.model_version_id ? `#${p.model_version_id}` : "none"} />
                    <Stat label="Provider" value={p.provider_code ?? "—"} />
                    <Stat label="Created" value={fmtDate(p.created_at)} />
                  </div>
                </SectionCard>
                <SectionCard title="Outcome tracking">
                  <div className="space-y-2 text-sm">
                    <Badge variant={p.outcome === "tp_hit" ? "buy" : p.outcome === "sl_hit" ? "sell" : "neutral"}>{p.outcome.replace("_", " ")}</Badge>
                    {p.outcome === "open" && <p className="text-xs text-muted-foreground">Open: neither stop nor target reached yet. Use “Refresh outcomes” on the Predictions page.</p>}
                    {p.outcome === "not_applicable" && <p className="text-xs text-muted-foreground">WAIT has no trade to track.</p>}
                    {p.outcome_meta && p.outcome !== "not_applicable" && (
                      <dl className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
                        {Object.entries(p.outcome_meta).filter(([, v]) => typeof v === "number" || typeof v === "string").map(([k, v]) => (
                          <div key={k} className="contents"><dt>{k.replace(/_/g, " ")}</dt><dd className="num text-foreground">{String(typeof v === "number" ? Math.round(v * 1e4) / 1e4 : v)}</dd></div>
                        ))}
                      </dl>
                    )}
                  </div>
                </SectionCard>
                {p.warnings && p.warnings.length > 0 && (
                  <SectionCard title="Warnings">
                    <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">{p.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                  </SectionCard>
                )}
                <AnalysisOnlyNotice />
              </aside>
            </div>
          </>
        );
      }}
    </QueryState>
  );
}

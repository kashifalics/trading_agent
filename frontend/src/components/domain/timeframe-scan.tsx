"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, QueryState } from "@/components/domain/common";
import { SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { usePatternScan, useSync } from "@/lib/hooks";
import type { EvidenceVerdict, PatternFiring } from "@/lib/types";
import { fmtNum, fmtPct } from "@/lib/utils";

export const SYNC_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1H", "2H", "4H", "1D", "1W", "1M"];

const VERDICT: Record<EvidenceVerdict, { label: string; variant: "buy" | "wait" | "sell" | "neutral"; help: string }> = {
  confirmed_tradeable: { label: "confirmed", variant: "buy", help: "Beat random entries out of sample AND profitable after costs" },
  confirmed_not_profitable_after_costs: { label: "informative, not profitable", variant: "wait", help: "Predictive out of sample, but costs exceed the edge" },
  failed_out_of_sample: { label: "failed OOS", variant: "sell", help: "Looked good in discovery, did not hold up on later data" },
  no_edge_found: { label: "no edge", variant: "neutral", help: "Did not beat taking the same trade at random" },
  too_few_events: { label: "too few events", variant: "neutral", help: "Not enough history to judge" },
  no_study_data: { label: "no track record", variant: "neutral", help: "No study data for this pattern/timeframe" },
};

function Firing({ f }: { f: PatternFiring }) {
  const v = VERDICT[f.verdict];
  const e = f.evidence;
  const title = `${v.help}${e ? ` | OOS n=${e.o_n ?? "—"}, win ${fmtPct(e.o_win ?? null)}, gross ${fmtNum(e.o_gross, 2)}R, net ${fmtNum(e.o_net, 2)}R, lift ${fmtNum(e.o_lift, 2)}R` : ""}`;
  return (
    <span className="mr-1.5 mb-1 inline-flex items-center gap-1" title={title}>
      <span className={f.side === "long" ? "text-bull" : "text-bear"}>{f.side === "long" ? "▲" : "▼"}</span>
      <span className="text-xs">{f.pattern.replace(/_/g, " ")}</span>
      <Badge variant={v.variant}>{v.label}</Badge>
    </span>
  );
}

export function AllTimeframesPanel({ symbol }: { symbol: string }) {
  const q = usePatternScan(symbol);
  const sync = useSync();
  const qc = useQueryClient();
  const [progress, setProgress] = useState<string | null>(null);
  const [failed, setFailed] = useState<string[]>([]);

  const syncAll = async () => {
    setFailed([]);
    const bad: string[] = [];
    for (const tf of SYNC_TIMEFRAMES) {
      setProgress(`Syncing ${symbol} ${tf}…`);
      try {
        await sync.mutateAsync({ symbol, timeframe: tf, bars: tf === "1W" ? 400 : tf === "1M" ? 100 : 1500 });
      } catch {
        bad.push(tf);
      }
    }
    setFailed(bad);
    setProgress(null);
    await qc.invalidateQueries({ queryKey: ["pattern-scan"] });
  };

  return (
    <SectionCard
      title={`${symbol} - every timeframe, right now`}
      actions={
        <Button size="sm" variant="outline" loading={!!progress} onClick={() => void syncAll()}>
          <Download className="h-3.5 w-3.5" /> Sync all timeframes
        </Button>
      }
    >
      {progress && <p role="status" className="mb-2 text-xs text-muted-foreground">{progress}</p>}
      {failed.length > 0 && <p className="mb-2 text-xs text-warn">Could not sync: {failed.join(", ")} (provider limits or unsupported on this plan).</p>}
      {sync.isError && failed.length === 0 && <ErrorState error={sync.error} />}
      <QueryState query={q} isEmpty={(d) => d.timeframes.every((f) => f.status !== "ok")}
        empty={<EmptyState title="No stored candles yet" hint="Press “Sync all timeframes” to download history for every timeframe, then this table fills in." />}>
        {(d) => (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge variant="buy">{d.alignment.bullish_timeframes} bullish</Badge>
              <Badge variant="sell">{d.alignment.bearish_timeframes} bearish</Badge>
              <span className="text-xs text-muted-foreground">of {d.alignment.analysed} timeframes with enough data (structure trend)</span>
            </div>
            <Table>
              <THead><TR><TH>TF</TH><TH className="text-right">Bars</TH><TH>Structure</TH><TH>Last break</TH><TH>Range zone</TH><TH className="text-right">Live zones</TH><TH>Patterns firing in the last {d.recent_bars} bars</TH></TR></THead>
              <TBody>
                {d.timeframes.map((f) => (
                  <TR key={f.timeframe}>
                    <TD className="font-medium">{f.timeframe}</TD>
                    <TD className="num text-right text-muted-foreground">{f.bars}</TD>
                    {f.status !== "ok" ? (
                      <TD colSpan={5} className="text-xs text-muted-foreground">insufficient stored data</TD>
                    ) : (
                      <>
                        <TD><Badge variant={f.structure_trend! > 0 ? "buy" : f.structure_trend! < 0 ? "sell" : "neutral"}>{f.structure_trend! > 0 ? "bullish" : f.structure_trend! < 0 ? "bearish" : "none"}</Badge></TD>
                        <TD className="text-xs text-muted-foreground">{f.last_break ?? "—"}</TD>
                        <TD className="text-xs">{f.zone ?? "—"}{f.range_position != null ? ` (${fmtPct(f.range_position)})` : ""}</TD>
                        <TD className="num text-right">{f.live_zones}</TD>
                        <TD>{f.patterns_firing?.length ? f.patterns_firing.map((p) => <Firing key={`${p.pattern}${p.side}`} f={p} />) : <span className="text-xs text-muted-foreground">none</span>}</TD>
                      </>
                    )}
                  </TR>
                ))}
              </TBody>
            </Table>
            <p className="text-[11px] leading-snug text-muted-foreground">{d.note}</p>
            <dl className="grid gap-x-6 gap-y-1 text-[11px] text-muted-foreground sm:grid-cols-2">
              {(Object.entries(VERDICT) as [EvidenceVerdict, (typeof VERDICT)[EvidenceVerdict]][]).map(([k, v]) => (
                <div key={k} className="flex gap-2"><dt><Badge variant={v.variant}>{v.label}</Badge></dt><dd>{v.help}</dd></div>
              ))}
            </dl>
          </div>
        )}
      </QueryState>
    </SectionCard>
  );
}

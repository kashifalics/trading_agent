"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CallBadge, ShortCall } from "@/components/domain/call";
import { Play, Radar } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { DecisionBadge, ErrorState, PageHeader, QueryState } from "@/components/domain/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/form";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/misc";
import { useInstruments, usePredictions, useRunAnalysis, useSignalsSummary } from "@/lib/hooks";
import type { SignalsSummaryItem } from "@/lib/signal-types";
import type { Instrument, Prediction } from "@/lib/types";
import { TIMEFRAME_CODES, cn, fmtNum, oldestTime, timeAgo } from "@/lib/utils";

const SCAN_TFS = TIMEFRAME_CODES;

function Cell({ pred, inst, tf, onRun, busy }: { pred?: Prediction; inst: Instrument; tf: string; onRun: () => void; busy: boolean }) {
  if (!inst.supported) return <TD className="text-xs text-muted-foreground">no data source</TD>;
  return (
    <TD>
      <div className="flex items-center gap-2">
        {pred ? (
          <Link href={`/predictions/${pred.id}`} className="flex items-center gap-2" title={`${inst.canonical_symbol} ${tf}: open this analysis`}>
            {pred.call ? <CallBadge call={pred.call} className="text-[10px]" /> : <DecisionBadge decision={pred.decision} />}
            <span className="num text-xs text-muted-foreground">{pred.confluence_score !== null ? fmtNum(pred.confluence_score, 2) : "—"}</span>
            <span className="text-[11px] text-muted-foreground">{timeAgo(pred.created_at)}</span>
          </Link>
        ) : (
          <span className="text-xs text-muted-foreground">not analysed</span>
        )}
        <Button size="icon" variant="ghost" aria-label={`Run ${inst.canonical_symbol} ${tf}`} disabled={busy} onClick={onRun}>
          <Play className="h-3.5 w-3.5" />
        </Button>
      </div>
    </TD>
  );
}

/** Live: the Signals engine's decision for every instrument and timeframe (refreshed by the backend every minute). */
function LiveMatrix() {
  const q = useSignalsSummary();
  const items: SignalsSummaryItem[] = q.data?.items ?? [];
  const tfs = TIMEFRAME_CODES;
  const at = oldestTime(items.map((i) => i.as_of));
  const count = (d: string) => items.reduce((n, i) => n + (i.tfs ?? []).filter((t) => t.decision === d).length, 0);
  return (
    <Card className="mb-5" data-testid="live-matrix">
      <CardHeader>
        <CardTitle>Live decisions: every instrument and timeframe</CardTitle>
        <span className="text-xs text-muted-foreground">
          {at ? `analysed ${timeAgo(at)} · ` : ""}refreshes automatically · {count("HOLD")} held paper trades · {count("WAIT")} WAIT · {count("NO TRADE")} NO TRADE ·{" "}
          {count("ENTER")} ENTER · click a cell for its checklist
        </span>
      </CardHeader>
      <CardContent className="p-0">
        <QueryState query={q} skeleton={<div className="space-y-2 p-4">{[0, 1, 2, 3, 4, 5].map((k) => <Skeleton key={k} className="h-9 w-full" />)}</div>}>
          {() => (
            <Table>
              <THead><TR><TH className="sticky left-0 z-10 bg-card">Instrument</TH>{tfs.map((tf) => <TH key={tf} className="text-center">{tf}</TH>)}</TR></THead>
              <TBody>
                {items.map((i) => {
                  const by = Object.fromEntries((i.tfs ?? []).map((t) => [t.timeframe, t]));
                  return (
                    <TR key={i.symbol} data-testid={`matrix-${i.symbol}`}>
                      <TD className="sticky left-0 z-10 bg-card font-medium">
                        <Link href={`/signals?symbol=${i.symbol}`} className="hover:underline">{i.symbol}</Link>
                        {i.status !== "ok" && <span className="block text-[11px] text-muted-foreground">{i.status === "failed" ? "analysis failed" : "no data yet"}</span>}
                      </TD>
                      {tfs.map((tf) => {
                        const t = by[tf];
                        const side = t?.direction && t.direction !== "NONE" ? t.direction : null;
                        return (
                          <TD key={tf} className="px-1.5 text-center">
                            {t ? (
                              <Link href={`/signals?symbol=${i.symbol}&tf=${tf}`} className="inline-flex flex-col items-center gap-0.5 rounded-md p-0.5 hover:bg-muted/60"
                                data-testid={`cell-${i.symbol}-${tf}`}>
                                <ShortCall label={t.label} decision={t.decision} headline={t.headline} />
                                <span className={cn("num text-[10px]", side === "BUY" ? "text-bull" : side === "SELL" ? "text-bear" : "text-muted-foreground")}>
                                  {side ?? ""}
                                  {t.unrealized_r != null ? ` ${t.unrealized_r >= 0 ? "+" : ""}${fmtNum(t.unrealized_r, 1)}R` : t.score != null ? ` ${t.score}` : ""}
                                </span>
                              </Link>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TD>
                        );
                      })}
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </QueryState>
      </CardContent>
      <p className="px-4 py-3 text-xs text-muted-foreground">
        Under each decision: the side and the setup score (0-100, setup quality, not a chance of winning), or the open result in R of a held
        paper trade. The same decisions as the Signals page; ENTER needs research-validated rules, so it does not appear today.
      </p>
    </Card>
  );
}

export default function ScannerPage() {
  const instruments = useInstruments();
  const preds = usePredictions({ limit: 200 });
  const run = useRunAnalysis();
  const qc = useQueryClient();
  const [tfs, setTfs] = useState<string[]>(["15m", "1H", "4H", "1D"]);
  const [scanning, setScanning] = useState(false);

  const latest = (sym: string, tf: string) => preds.data?.items.find((p) => p.symbol === sym && p.timeframe === tf);
  const poll = () => {
    let n = 0;
    const t = setInterval(() => {
      void qc.invalidateQueries({ queryKey: ["predictions"] });
      if (++n >= 12) {
        clearInterval(t);
        setScanning(false);
      }
    }, 3000);
  };
  const runOne = (symbol: string, timeframe: string) => {
    run.mutate({ symbol, timeframe, mtf: {}, lookback_bars: 1500, auto_sync: true });
    setScanning(true);
    poll();
  };
  const scanAll = async () => {
    setScanning(true);
    for (const i of (instruments.data ?? []).filter((x) => x.supported))
      for (const tf of tfs) await run.mutateAsync({ symbol: i.canonical_symbol, timeframe: tf, mtf: {}, lookback_bars: 1500, auto_sync: true }).catch(() => undefined);
    poll();
  };

  return (
    <>
      <PageHeader
        title="Market Scanner"
        description="Every instrument and timeframe on one screen: the live decision from the Signals engine (updated every minute), and below it the stored deep analyses (decision engine with historical analogues) that you can run on demand."
        actions={<Button onClick={() => void scanAll()} loading={scanning}><Radar className="h-4 w-4" /> Run deep analysis</Button>}
      />
      <LiveMatrix />
      <h2 className="mb-1 text-base font-semibold">Deep analysis (stored, run on demand)</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        The older decision engine with historical analogues and models, run for the ticked timeframes when you press Run deep analysis or
        a play button. Each result keeps its time; it is not refreshed automatically.
      </p>
      <div className="mb-3 flex flex-wrap gap-4">
        {SCAN_TFS.map((tf) => (
          <Checkbox key={tf} label={tf} checked={tfs.includes(tf)} onChange={(e) => setTfs((cur) => (e.target.checked ? [...cur, tf] : cur.filter((x) => x !== tf)))} />
        ))}
      </div>
      {run.isError && <div className="mb-3"><ErrorState error={run.error} /></div>}
      <Card>
        <CardContent className="p-0">
          <QueryState query={instruments}>
            {(list) => (
              <Table>
                <THead><TR><TH>Instrument</TH>{tfs.map((tf) => <TH key={tf}>{tf}</TH>)}</TR></THead>
                <TBody>
                  {list.map((i) => (
                    <TR key={i.id}>
                      <TD>
                        <div className="font-medium">{i.canonical_symbol}</div>
                        {!i.supported && <Badge variant="wait">unsupported</Badge>}
                      </TD>
                      {tfs.map((tf) => (
                        <Cell key={tf} pred={latest(i.canonical_symbol, tf)} inst={i} tf={tf} busy={run.isPending} onRun={() => runOne(i.canonical_symbol, tf)} />
                      ))}
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Play, Radar } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { DecisionBadge, ErrorState, PageHeader, QueryState } from "@/components/domain/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/form";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useInstruments, usePredictions, useRunAnalysis } from "@/lib/hooks";
import type { Instrument, Prediction } from "@/lib/types";
import { fmtNum, timeAgo } from "@/lib/utils";

const SCAN_TFS = ["15m", "1H", "4H", "1D"];

function Cell({ pred, inst, tf, onRun, busy }: { pred?: Prediction; inst: Instrument; tf: string; onRun: () => void; busy: boolean }) {
  if (!inst.supported) return <TD className="text-xs text-muted-foreground">no data source</TD>;
  return (
    <TD>
      <div className="flex items-center gap-2">
        {pred ? (
          <Link href={`/predictions/${pred.id}`} className="flex items-center gap-2" aria-label={`${inst.canonical_symbol} ${tf} ${pred.decision}`}>
            <DecisionBadge decision={pred.decision} />
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

export default function ScannerPage() {
  const instruments = useInstruments();
  const preds = usePredictions({ limit: 200 });
  const run = useRunAnalysis();
  const qc = useQueryClient();
  const [tfs, setTfs] = useState<string[]>(["1H", "4H"]);
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
        description="Latest stored decision per instrument and timeframe. Results are real analyses run by the backend; instruments without a data source are shown as such."
        actions={<Button onClick={() => void scanAll()} loading={scanning}><Radar className="h-4 w-4" /> Scan supported instruments</Button>}
      />
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

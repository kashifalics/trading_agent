"use client";

import { RefreshCw } from "lucide-react";
import { CallBadge } from "@/components/domain/call";
import Link from "next/link";
import { useState } from "react";
import { DecisionBadge, EmptyState, PageHeader, QueryState } from "@/components/domain/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useInstruments, usePredictions, useRefreshOutcomes } from "@/lib/hooks";
import { fmtDate, fmtNum, fmtPrice } from "@/lib/utils";

const PAGE = 20;

export default function PredictionsPage() {
  const [symbol, setSymbol] = useState("");
  const [decision, setDecision] = useState("");
  const [outcome, setOutcome] = useState("");
  const [offset, setOffset] = useState(0);
  const instruments = useInstruments();
  const q = usePredictions({ symbol: symbol || undefined, decision: decision || undefined, outcome: outcome || undefined, limit: PAGE, offset });
  const refresh = useRefreshOutcomes();
  const reset = (fn: () => void) => { fn(); setOffset(0); };

  return (
    <>
      <PageHeader
        title="Predictions"
        description="Every analysis is stored with its evidence and tracked against subsequent candles, independently of any backtest. Each row shows the decision (ENTER, WAIT or NO TRADE); the rules behind these analyses have no verified out-of-sample edge, so none is ENTER."
        actions={<Button variant="outline" loading={refresh.isPending} onClick={() => refresh.mutate()}><RefreshCw className="h-4 w-4" /> Refresh outcomes</Button>}
      />
      <div className="mb-3 grid max-w-2xl grid-cols-3 gap-2">
        <Select aria-label="Filter instrument" value={symbol} onChange={(e) => reset(() => setSymbol(e.target.value))}>
          <option value="">All instruments</option>
          {instruments.data?.map((i) => <option key={i.id} value={i.canonical_symbol}>{i.canonical_symbol}</option>)}
        </Select>
        <Select aria-label="Filter decision" value={decision} onChange={(e) => reset(() => setDecision(e.target.value))}>
          <option value="">All decisions</option><option>BUY</option><option>SELL</option><option>WAIT</option>
        </Select>
        <Select aria-label="Filter outcome" value={outcome} onChange={(e) => reset(() => setOutcome(e.target.value))}>
          <option value="">All outcomes</option><option value="open">open</option><option value="tp_hit">tp_hit</option><option value="sl_hit">sl_hit</option><option value="expired">expired</option><option value="not_applicable">not_applicable</option>
        </Select>
      </div>
      <Card>
        <CardContent className="p-0">
          <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<div className="p-4"><EmptyState title="No predictions match" hint="Run an analysis from Chart Analysis or the Scanner." /></div>}>
            {(d) => (
              <>
                <Table>
                  <THead><TR><TH>#</TH><TH>Instrument</TH><TH>TF</TH><TH>Decision</TH><TH>Entry</TH><TH>Stop</TH><TH>Target 1</TH><TH>R:R</TH><TH>Quality</TH><TH>Outcome</TH><TH>As of</TH></TR></THead>
                  <TBody>
                    {d.items.map((p) => {
                      const lv = p.call?.levels ?? p.call?.hypothetical ?? null; // ENTER levels, or hypothetical ones in experimental mode
                      return (
                      <TR key={p.id}>
                        <TD><Link className="text-primary hover:underline" href={`/predictions/${p.id}`}>{p.id}</Link></TD>
                        <TD className="font-medium">{p.symbol}</TD><TD>{p.timeframe}</TD>
                        <TD>{p.call ? <CallBadge call={p.call} className="text-[10px]" /> : <DecisionBadge decision={p.decision} />}</TD>
                        <TD className={lv && !p.call?.levels ? "num text-muted-foreground" : "num"}>{lv ? (lv.entry_zone ? `${fmtPrice(lv.entry_zone[0])}–${fmtPrice(lv.entry_zone[1])}` : fmtPrice(lv.entry)) : "—"}</TD>
                        <TD className="num">{lv ? fmtPrice(lv.stop_loss) : "—"}</TD>
                        <TD className="num">{lv?.targets[0] ? fmtPrice(lv.targets[0].price) : "—"}</TD>
                        <TD className="num">{lv?.risk_reward ? fmtNum(lv.risk_reward, 2) : "—"}</TD>
                        <TD className="num">{fmtNum(p.data_quality_score, 2)}</TD>
                        <TD><Badge variant={p.outcome === "tp_hit" ? "buy" : p.outcome === "sl_hit" ? "sell" : "neutral"}>{p.outcome.replace("_", " ")}</Badge></TD>
                        <TD className="num text-muted-foreground">{fmtDate(p.as_of_ts)}</TD>
                      </TR>
                      );
                    })}
                  </TBody>
                </Table>
                <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
                  <span>{d.offset + 1}–{Math.min(d.offset + PAGE, d.total)} of {d.total}</span>
                  <span className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</Button>
                    <Button size="sm" variant="outline" disabled={offset + PAGE >= d.total} onClick={() => setOffset(offset + PAGE)}>Next</Button>
                  </span>
                </div>
              </>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </>
  );
}

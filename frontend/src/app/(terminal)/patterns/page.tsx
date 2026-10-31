"use client";

import { useMemo, useState } from "react";
import { EmptyState, InstrumentSelect, PageHeader, QueryState, TimeframeSelect } from "@/components/domain/common";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/form";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { usePatternDefinitions, usePatterns } from "@/lib/hooks";
import { useSettings } from "@/lib/store";
import { fmtDate, fmtPrice } from "@/lib/utils";

export default function PatternsPage() {
  const s = useSettings();
  const q = usePatterns(s.symbol, s.timeframe);
  const defs = usePatternDefinitions();
  const [kind, setKind] = useState("");
  const events = useMemo(() => (q.data?.events ?? []).filter((e) => !kind || e.kind === kind).slice().reverse(), [q.data, kind]);
  const allDefs = { ...(defs.data?.candlestick ?? {}), ...(defs.data?.price_action ?? {}) };

  return (
    <>
      <PageHeader title="Historical Patterns" description="Deterministic detections on stored, completed candles. Each has an operational definition, the bar at which it became knowable, and price levels. A detection is description, not a trade signal." />
      <div className="mb-4 grid max-w-xl grid-cols-2 gap-3">
        <div><Label htmlFor="p-sym">Instrument</Label><InstrumentSelect id="p-sym" value={s.symbol} onChange={(v) => s.set({ symbol: v })} /></div>
        <div><Label htmlFor="p-tf">Timeframe</Label><TimeframeSelect id="p-tf" value={s.timeframe} onChange={(v) => s.set({ timeframe: v })} /></div>
      </div>
      <QueryState query={q}>
        {(d) =>
          d.events.length === 0 ? (
            <EmptyState title="No detections" hint={d.message ?? "No events in this window."} />
          ) : (
            <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
              <Card>
                <CardHeader><CardTitle>Counts · {d.n_bars} bars</CardTitle></CardHeader>
                <CardContent className="space-y-1 text-sm">
                  {Object.entries(d.counts ?? {}).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
                    <button key={k} onClick={() => setKind(kind === k ? "" : k)} className={`flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-muted ${kind === k ? "bg-muted" : ""}`}>
                      <span>{k.replace(/_/g, " ")}</span><span className="num text-muted-foreground">{n}</span>
                    </button>
                  ))}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Events{kind ? ` · ${kind}` : ""}</CardTitle>
                  <Select aria-label="Filter kind" className="w-48" value={kind} onChange={(e) => setKind(e.target.value)}>
                    <option value="">All kinds</option>
                    {Object.keys(d.counts ?? {}).map((k) => <option key={k} value={k}>{k}</option>)}
                  </Select>
                </CardHeader>
                <CardContent className="max-h-[560px] overflow-auto p-0">
                  <Table>
                    <THead><TR><TH>Confirmed</TH><TH>Kind</TH><TH>Dir</TH><TH className="text-right">Level / zone</TH><TH>Status</TH><TH>Evidence</TH></TR></THead>
                    <TBody>
                      {events.slice(0, 300).map((e, i) => (
                        <TR key={`${e.ts}${e.kind}${i}`}>
                          <TD className="num whitespace-nowrap">{fmtDate(e.time)}</TD>
                          <TD>{e.kind.replace(/_/g, " ")}</TD>
                          <TD><Badge variant={e.direction === "bullish" ? "buy" : e.direction === "bearish" ? "sell" : "neutral"}>{e.direction}</Badge></TD>
                          <TD className="num whitespace-nowrap text-right">{e.low !== null && e.high !== null ? `${fmtPrice(e.low)} – ${fmtPrice(e.high)}` : fmtPrice(e.price)}</TD>
                          <TD className="text-muted-foreground">{e.status ?? ""}</TD>
                          <TD className="max-w-md text-xs text-muted-foreground">{e.evidence}</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )
        }
      </QueryState>
      <Card className="mt-4">
        <CardHeader><CardTitle>Operational definitions</CardTitle></CardHeader>
        <CardContent>
          <dl className="grid gap-x-8 gap-y-2 text-sm md:grid-cols-2">
            {Object.entries(allDefs).map(([k, v]) => (
              <div key={k}><dt className="font-medium">{k.replace(/_/g, " ")}</dt><dd className="text-xs text-muted-foreground">{v}</dd></div>
            ))}
          </dl>
          {defs.data && <p className="mt-3 text-xs text-muted-foreground">{defs.data.note}</p>}
        </CardContent>
      </Card>
    </>
  );
}

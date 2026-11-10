"use client";

import { Play } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, PageHeader, QueryState } from "@/components/domain/common";
import { AccountCard, Breakdowns, EquityCurve, ForwardStats, TradesTable, VerdictCard, WorkerLine } from "@/components/domain/paper";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton, Tabs } from "@/components/ui/misc";
import { usePaperSummary, usePaperTrades, useRunPaperCycle } from "@/lib/hooks";
import type { PaperRunResult } from "@/lib/paper-types";

type HistoryTab = "closed" | "unfilled" | "finished";
const HISTORY_TABS: { id: HistoryTab; label: string }[] = [
  { id: "closed", label: "Closed" },
  { id: "unfilled", label: "Never filled" },
  { id: "finished", label: "All finished" },
];

function cycleText(r: PaperRunResult): string {
  const added = r.results.reduce((n, x) => n + x.new.length, 0);
  const changed = r.results.reduce((n, x) => n + x.updated.length, 0);
  const failed = r.results.filter((x) => x.status === "failed").map((x) => x.symbol);
  return `Cycle finished in ${r.duration_s.toFixed(1)}s: ${added} new signal${added === 1 ? "" : "s"}, ${changed} trade update${changed === 1 ? "" : "s"}${failed.length ? `; failed: ${failed.join(", ")}` : ""}.`;
}

function History() {
  const [tab, setTab] = useState<HistoryTab>("closed");
  const q = usePaperTrades(tab);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trade history</CardTitle>
        <Tabs tabs={HISTORY_TABS} value={tab} onChange={setTab} />
      </CardHeader>
      <CardContent className="p-0">
        <QueryState
          query={q}
          isEmpty={(d) => d.items.length === 0}
          empty={<div className="p-4"><EmptyState title="Nothing here yet" hint="Finished paper trades are listed here, newest first. Click a row to see the plan as it was when the signal fired." /></div>}
        >
          {(d) => <TradesTable trades={d.items} kind="history" />}
        </QueryState>
      </CardContent>
    </Card>
  );
}

export default function PaperTradingPage() {
  const summary = usePaperSummary();
  const run = useRunPaperCycle();
  return (
    <>
      <PageHeader
        title="Paper Trading"
        description="Every EXECUTE NOW and PLACE LIMIT ORDER signal is recorded the moment the backend sees it, then traded on paper against the candles that follow. Simulated orders only: no broker, no real money."
        actions={<Button onClick={() => run.mutate()} loading={run.isPending}><Play className="h-4 w-4" aria-hidden /> Run cycle now</Button>}
      />
      <div className="space-y-5">
        {run.isError && <ErrorState error={run.error} />}
        {run.data && <p className="text-sm text-muted-foreground" role="status">{cycleText(run.data)}</p>}
        <QueryState query={summary} skeleton={<Skeleton className="h-64 w-full" />}>
          {(s) => (
            <div className="space-y-5">
              <WorkerLine w={s.worker} />
              <VerdictCard s={s} />
              <Card>
                <CardHeader>
                  <CardTitle>Forward test</CardTitle>
                  <span className="text-xs text-muted-foreground">every recorded signal, whether or not the account took it</span>
                </CardHeader>
                <CardContent><ForwardStats s={s} /></CardContent>
              </Card>
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Cumulative R</CardTitle>
                    <span className="text-xs text-muted-foreground">closed paper trades in order, net of the spread</span>
                  </CardHeader>
                  <CardContent><EquityCurve label="Cumulative R" points={s.forward.equity_curve.map((p) => ({ t: p.t, v: p.r }))} /></CardContent>
                </Card>
                <AccountCard a={s.account} />
              </div>
              <Card>
                <CardHeader><CardTitle>Open positions ({s.open.length})</CardTitle></CardHeader>
                <CardContent className="p-0">
                  {s.open.length ? <TradesTable trades={s.open} kind="open" /> : <div className="p-4"><EmptyState title="No open positions" hint="A market signal fills at the next candle's open; a limit order opens when its price trades." /></div>}
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Pending orders ({s.pending.length})</CardTitle></CardHeader>
                <CardContent className="p-0">
                  {s.pending.length ? <TradesTable trades={s.pending} kind="pending" /> : <div className="p-4"><EmptyState title="No pending orders" hint="Limit orders rest here until they fill, expire, get invalidated or TP1 trades first." /></div>}
                </CardContent>
              </Card>
              <History />
              <Card>
                <CardHeader><CardTitle>Breakdown</CardTitle></CardHeader>
                <CardContent><Breakdowns s={s} /></CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>How paper trades are simulated</CardTitle></CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">{s.method.map((m) => <li key={m}>{m}</li>)}</ul>
                  <p className="mt-3 text-xs text-muted-foreground">{s.disclaimer}</p>
                </CardContent>
              </Card>
            </div>
          )}
        </QueryState>
      </div>
    </>
  );
}

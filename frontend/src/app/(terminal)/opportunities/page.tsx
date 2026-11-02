"use client";

import { Info, RefreshCw, ScanSearch } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, PageHeader, QueryState } from "@/components/domain/common";
import {
  InstrumentStatus,
  OpportunityDetailView,
  OpportunityTable,
  StyleCard,
  SummaryBar,
  TimeframeMatrix,
  ValidationPanel,
} from "@/components/domain/opportunities";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { useInstruments, useOppSummary, useStartScan } from "@/lib/hooks";
import type { OppSummary } from "@/lib/opportunity-types";

function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warn" }) {
  return (
    <p role="note" className={`flex items-start gap-2 rounded-md border p-3 text-sm ${tone === "warn" ? "border-warn/30 bg-warn/5 text-warn" : "border-primary/30 bg-primary/5 text-muted-foreground"}`}>
      <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

function Content({ s, selected, onSelect }: { s: OppSummary; selected: number | null; onSelect: (id: number) => void }) {
  const inst = useInstruments();
  const precision = (sym: string) => inst.data?.find((i) => i.canonical_symbol === sym)?.price_precision ?? 2;
  const live = s.ranking.filter((r) => r.direction === "BUY" || r.direction === "SELL");
  const anyValidated = s.ranking.some((r) => r.validation_status === "validated");
  const first = s.ranking.find((r) => r.rank !== null) ?? s.ranking[0];
  const sel = selected ?? first?.id ?? null;

  if (!s.scan) {
    return (
      <div className="space-y-4">
        <SummaryBar s={s} />
        <EmptyState title={s.running_scan ? "First scan in progress…" : "No scan has been run yet"}
          hint="A scan analyses every supported instrument on all 14 timeframes from your stored candles, then ranks the setups it finds. Sync data first (Historical Patterns → Sync all timeframes) if no candles are stored." />
      </div>
    );
  }
  return (
    <div className="space-y-5">
      <SummaryBar s={s} />
      {live.length === 0 && <Notice>No setup currently meets the required criteria on any instrument and style. <strong>WAIT is a valid result</strong> — the reasons are listed on each card.</Notice>}
      {!anyValidated && (
        <Notice tone="warn">
          No setup rule set has passed out-of-sample validation. Every score below is an <strong>evidence-quality score, not a win probability</strong>, and is capped by the strategy&apos;s validation status.
          Past patterns do not guarantee future results. Analysis only: nothing is executed.
        </Notice>
      )}
      <section aria-label="Best opportunity per trading style" className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {s.styles.map((st) => <StyleCard key={st.style} item={st} onSelect={onSelect} precision={precision} />)}
      </section>
      <Card>
        <CardHeader><CardTitle>Market read by timeframe</CardTitle><span className="text-xs text-muted-foreground">what each timeframe is doing, even when no setup qualifies</span></CardHeader>
        <CardContent><TimeframeMatrix items={s.instruments} /></CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Consolidated ranking</CardTitle><span className="text-xs text-muted-foreground">validated setups outrank unvalidated ones; same-instrument, same-direction setups are one exposure (≈#)</span></CardHeader>
        <CardContent className="p-0"><OpportunityTable rows={s.ranking} selected={sel} onSelect={onSelect} precision={precision} /></CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Instruments and timeframes</CardTitle><span className="text-xs text-muted-foreground">unsupported or empty sources are shown, never substituted</span></CardHeader>
        <CardContent><InstrumentStatus items={s.instruments} /></CardContent>
      </Card>
      {sel !== null && <OpportunityDetailView id={sel} />}
      <Card>
        <CardHeader><CardTitle>Strategy validation</CardTitle><span className="text-xs text-muted-foreground">out-of-sample results, including the negative ones</span></CardHeader>
        <CardContent><ValidationPanel /></CardContent>
      </Card>
    </div>
  );
}

export default function OpportunitiesPage() {
  const q = useOppSummary();
  const scan = useStartScan();
  const [selected, setSelected] = useState<number | null>(null);
  const running = !!q.data?.running_scan || scan.isPending;
  return (
    <>
      <PageHeader
        title="Trade Opportunities"
        description="Automatic multi-timeframe analysis of every supported instrument, ranked by evidence quality. WAIT is a valid answer. Analysis only: no orders are placed and no broker is connected."
        actions={
          <>
            <Button onClick={() => scan.mutate({})} disabled={running} data-testid="run-scan"><ScanSearch className="h-4 w-4" /> {running ? "Scanning…" : "Run scan"}</Button>
            <Button variant="outline" onClick={() => scan.mutate({ refresh_data: true })} disabled={running} title="Syncs stale timeframes from the data providers first (uses provider quota)">
              <RefreshCw className="h-4 w-4" /> Refresh data &amp; scan
            </Button>
          </>
        }
      />
      {scan.isError && <div className="mb-4"><ErrorState error={scan.error} /></div>}
      {scan.data?.deduplicated && <div className="mb-4"><Notice>A scan is already running (#{scan.data.id}); showing its progress instead of starting another.</Notice></div>}
      <QueryState query={q} skeleton={<Skeleton className="h-64 w-full" />}>
        {(s) => <Content s={s} selected={selected} onSelect={setSelected} />}
      </QueryState>
    </>
  );
}

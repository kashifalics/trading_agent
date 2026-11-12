"use client";

import { Info, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState, PageHeader, QueryState } from "@/components/domain/common";
import { CallCard } from "@/components/domain/call";
import { AllSignalsTable, InstrumentTabs, OverviewCard, PlanDetail, TimeframeTable, isActionable } from "@/components/domain/signals";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { useSignal, useSignalsSummary, useSyncSignal } from "@/lib/hooks";
import type { SignalAnalysis } from "@/lib/signal-types";
import { useSettings } from "@/lib/store";
import { oldestTime, timeAgo } from "@/lib/utils";

const AUTO_SYNC_MS = 60_000;

function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warn" }) {
  return (
    <p role="note" className={`flex items-start gap-2 rounded-md border p-3 text-sm ${tone === "warn" ? "border-warn/30 bg-warn/5 text-warn" : "border-primary/30 bg-primary/5 text-muted-foreground"}`}>
      <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

function defaultTf(a: SignalAnalysis): string {
  return a.call?.timeframe ?? a.best?.timeframe ?? a.plans.find((p) => isActionable(p.state))?.timeframe ?? a.plans.find((p) => p.state === "WATCHLIST")?.timeframe ?? "1H";
}

function Analysis({ a, tf, setTf }: { a: SignalAnalysis; tf: string | null; setTf: (tf: string) => void }) {
  if (a.status !== "ok") {
    return (
      <div className="space-y-4">
        {a.call && <CallCard call={a.call} symbol={a.symbol} precision={a.price_precision} title="Decision now" />}
        <EmptyState title={`${a.symbol}: no analysis yet`} hint={`${a.reason ?? "No stored candles."} Press "Refresh now" to load candles from ${a.provider}.`} />
      </div>
    );
  }
  const sel = tf && a.plans.some((p) => p.timeframe === tf) ? tf : defaultTf(a);
  const select = (t: string) => {
    setTf(t);
    if (typeof document !== "undefined") document.getElementById("plan-detail")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };
  return (
    <div className="space-y-5">
      {a.call && (
        <div className="space-y-1">
          <CallCard call={a.call} symbol={a.symbol} precision={a.price_precision} title="Decision now" />
          {a.call.timeframe && <button className="text-xs font-medium text-primary hover:underline" onClick={() => select(a.call!.timeframe!)}>Technical detail for {a.call.timeframe} ↓</button>}
        </div>
      )}
      <OverviewCard a={a} />
      <Card>
        <CardHeader>
          <CardTitle>All timeframes</CardTitle>
          <span className="text-xs text-muted-foreground">each timeframe is analysed top-down (higher-timeframe bias → setup → lower-timeframe confirmation); click a row for its checklist</span>
        </CardHeader>
        <CardContent className="p-0"><TimeframeTable a={a} selected={sel} onSelect={select} /></CardContent>
      </Card>
      <div id="plan-detail"><PlanDetail a={a} tf={sel} /></div>
      <p className="text-xs text-muted-foreground">{a.news_filter?.note} {a.disclaimer} Generated {timeAgo(a.generated_at)} · engine {a.config_version}.</p>
    </div>
  );
}

export default function SignalsPage() {
  const summary = useSignalsSummary();
  const [symbol, setSymbol] = useState<string | null>(null);
  const [tf, setTf] = useState<string | null>(null);
  useEffect(() => {
    // deep link from Overview "Decisions now": /signals?symbol=XAUUSD
    const s = new URLSearchParams(window.location.search).get("symbol");
    if (s) setSymbol(s.toUpperCase());
  }, []);
  const { liveSignals, experimentalMode, set } = useSettings();
  const sync = useSyncSignal();
  const { mutate } = sync;
  const items = summary.data?.items ?? [];
  const current = symbol ?? items.find((i) => i.status === "ok" && i.best)?.symbol ?? items.find((i) => i.status === "ok")?.symbol ?? items[0]?.symbol ?? null;
  const q = useSignal(current);

  useEffect(() => {
    if (!current || !liveSignals) return;
    mutate(current);
    const id = setInterval(() => mutate(current), AUTO_SYNC_MS);
    return () => clearInterval(id);
  }, [current, liveSignals, mutate]);

  return (
    <>
      <PageHeader
        title="Signals"
        description="Top-down multi-timeframe price-action analysis: one decision per instrument and timeframe (ENTER, WAIT, EXIT or NO TRADE) with its reasons, what must happen next and a 100-point confluence checklist. Entry, stop and targets appear only with ENTER. Analysis only: no orders are placed."
        actions={
          <>
            <Checkbox label="Live refresh (fetch new candles every 60 s)" checked={liveSignals} onChange={(e) => set({ liveSignals: e.target.checked })} />
            <Checkbox label="Experimental mode (show unvalidated levels)" checked={experimentalMode} onChange={(e) => set({ experimentalMode: e.target.checked })} />
            <Button onClick={() => current && mutate(current)} disabled={!current || sync.isPending} data-testid="refresh-now">
              <RefreshCw className={`h-4 w-4 ${sync.isPending ? "animate-spin" : ""}`} /> {sync.isPending ? "Refreshing…" : "Refresh now"}
            </Button>
          </>
        }
      />
      <div className="mb-4 space-y-2">
        <Notice tone="warn">
          Every instrument and timeframe gets one decision: <strong>ENTER</strong>, <strong>WAIT</strong>, <strong>EXIT</strong> or{" "}
          <strong>NO TRADE</strong>. ENTER requires every mandatory condition <em>and</em> research-validated rules; none has passed
          out-of-sample validation, so a technically complete setup is shown as <strong>WAIT — UNVALIDATED SETUP</strong>. The score measures
          setup quality, not the chance of winning, and no win probability is shown. High-impact news is not filtered.
          {experimentalMode && <> Experimental mode is on: hypothetical levels of unvalidated setups are shown, clearly marked.</>}
        </Notice>
        {sync.isError && <ErrorState error={sync.error} />}
        {sync.data && sync.data.notes.length > 0 && <Notice>{sync.data.notes.slice(0, 3).join(" · ")}</Notice>}
        {sync.data && !sync.data.synced && <Notice>{sync.data.notes[0]}</Notice>}
      </div>
      <QueryState query={summary} skeleton={<Skeleton className="h-16 w-full" />} isEmpty={(d) => d.items.length === 0}
        empty={<EmptyState title="No instruments configured" hint="Set SIGNAL_SYMBOLS in the backend .env." />}>
        {(d) => (
          <div className="space-y-5">
            <Card>
              <CardHeader>
                <CardTitle>All signals ({d.items.length} instruments)</CardTitle>
                <span className="text-xs text-muted-foreground" data-testid="all-signals-updated">
                  {oldestTime(d.items.map((i) => i.as_of)) ? `analysed ${timeAgo(oldestTime(d.items.map((i) => i.as_of))!)}` : ""} · refreshes automatically · click an instrument or a timeframe for its detail
                </span>
              </CardHeader>
              <CardContent className="p-0">
                <AllSignalsTable items={d.items} value={current} onPick={(s, t) => {
                  setSymbol(s);
                  setTf(t ?? null);
                  if (typeof document !== "undefined") document.getElementById("signal-detail")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
                }} />
              </CardContent>
            </Card>
            <div id="signal-detail" className="space-y-5">
            <InstrumentTabs items={d.items} value={current} onChange={(s) => { setSymbol(s); setTf(null); }} />
            <QueryState query={q} skeleton={<Skeleton className="h-96 w-full" />}>
              {(a) => <Analysis a={a} tf={tf} setTf={setTf} />}
            </QueryState>
            </div>
          </div>
        )}
      </QueryState>
    </>
  );
}

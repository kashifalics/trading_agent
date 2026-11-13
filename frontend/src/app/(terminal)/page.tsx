"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/misc";
import { CallBadge } from "@/components/domain/call";
import { ActionBadge } from "@/components/domain/engine";
import { DecisionBadge, EmptyState, ErrorState, JobBadge, PageHeader, QueryState } from "@/components/domain/common";
import { AnalysisOnlyNotice } from "@/components/domain/decision";
import { useAnalyses, useCoverage, useInstruments, useModels, usePatterns, usePredictions, useQuotes, useEngineSummary } from "@/lib/hooks";
import type { Instrument, Quote } from "@/lib/types";
import { useSettings } from "@/lib/store";
import { fmtDate, fmtNum, fmtPrice, timeAgo } from "@/lib/utils";

const STATUS_TEXT: Record<Quote["status"], string> = {
  ok: "live",
  unsupported: "No data source configured",
  not_configured: "API key required",
  error: "Quote unavailable",
};

function QuoteCard({ inst, quote }: { inst: Instrument; quote?: Quote }) {
  // Show the mapping that actually served the quote, not simply the first one registered.
  const map = inst.mappings.find((m) => m.provider === quote?.provider) ?? inst.mappings[0];
  // A last-known price (market closed, stale quote) is never labelled live.
  const delayed = quote?.status === "ok" && (quote.delayed ?? Boolean(quote.message));
  return (
    <Card data-testid={`quote-${inst.canonical_symbol}`}>
      <CardContent className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">{inst.canonical_symbol}</span>
          <Badge variant={quote?.status === "ok" ? (delayed ? "wait" : "buy") : "neutral"}>
            {quote ? (delayed ? "delayed" : STATUS_TEXT[quote.status]) : "…"}
          </Badge>
        </div>
        <div className="truncate text-xs text-muted-foreground">{inst.name}</div>
        {quote?.status === "ok" ? (
          <div className={delayed ? "num text-2xl font-semibold text-muted-foreground" : "num text-2xl font-semibold"}>{fmtPrice(quote.price, inst.price_precision)}</div>
        ) : (
          <div className="num text-2xl font-semibold text-muted-foreground">—</div>
        )}
        <div className="text-[11px] text-muted-foreground">
          {quote?.status === "ok"
            ? delayed ? quote.message ?? `last known price · ${timeAgo(quote.time)}` : `${quote.provider} · ${timeAgo(quote.time)}`
            : quote?.message ?? "loading"}
        </div>
        {map && <div className="text-[11px] text-muted-foreground">mapping: {map.provider} · {map.market_kind} · {map.status}</div>}
      </CardContent>
    </Card>
  );
}

function DirectionRow({ inst }: { inst: Instrument }) {
  const q = usePatterns(inst.canonical_symbol, "1H", inst.supported);
  let text = "No data source";
  let variant: "neutral" | "buy" | "sell" | "wait" = "neutral";
  if (inst.supported) {
    if (q.isLoading) text = "…";
    else if (q.isError || !q.data || q.data.n_bars < 30) text = "No stored candles";
    else if (q.data.structure_trend === 1) [text, variant] = ["Bullish structure", "buy"];
    else if (q.data.structure_trend === -1) [text, variant] = ["Bearish structure", "sell"];
    else [text, variant] = ["Undetermined", "wait"];
  }
  return (
    <TR>
      <TD className="font-medium">{inst.canonical_symbol}</TD>
      <TD>
        <Badge variant={variant}>{text}</Badge>
      </TD>
      <TD className="num text-right text-muted-foreground">{q.data?.atr ? `ATR ${fmtNum(q.data.atr, inst.price_precision)}` : ""}</TD>
    </TR>
  );
}

/** One action per instrument from the strategy engine (BUY / SELL / WAIT FOR BUY / WAIT FOR SELL / EXIT / NO TRADE), the same as Signals. */
function DecisionsNow() {
  const q = useEngineSummary();
  const experimental = useSettings((s) => s.experimentalMode);
  return (
    <Card data-testid="decisions-now">
      <CardHeader>
        <CardTitle>Decisions now</CardTitle>
        <span className="flex items-center gap-3 text-xs">
          {q.data && (
            <span className="text-muted-foreground" data-testid="decisions-updated">analysed {timeAgo(q.data.generated_at)} · refreshes automatically</span>
          )}
          <Link href="/signals" className="text-primary hover:underline">All signals</Link>
        </span>
      </CardHeader>
      <CardContent className="p-0">
        <QueryState query={q} isEmpty={(d) => d.items.length === 0} empty={<div className="p-4"><EmptyState title="No instruments" /></div>}
          skeleton={<div className="space-y-2 p-4"><p className="text-xs text-muted-foreground">Loading the decision for every instrument…</p>{[0, 1, 2, 3].map((k) => <Skeleton key={k} className="h-8 w-full" />)}</div>}>
          {(d) => (
            <Table>
              <THead><TR><TH>Instrument</TH><TH>Decision</TH><TH>Entry · SL · TP1</TH><TH>Next</TH></TR></THead>
              <TBody>
                {d.items.map((i) => {
                  const o = i.opportunity;
                  const p = i.price_precision ?? 2;
                  const action = i.primary.action === "EXIT" ? "EXIT" : o ? o.action : i.primary.action;
                  return (
                    <TR key={i.symbol}>
                      <TD className="font-medium">
                        <Link href="/signals" className="hover:underline">{i.symbol}</Link>
                        <span className="block text-[11px] text-muted-foreground">{o ? `${o.timeframe} · ${o.strategy_name}` : ""}</span>
                      </TD>
                      <TD><ActionBadge action={action} className="text-[10px]" /></TD>
                      <TD className="num whitespace-nowrap text-xs" data-testid={`levels-${i.symbol}`}>
                        {o?.plan ? (experimental || o.research_status === "VALIDATED"
                          ? `${fmtPrice(o.plan.entry, p)} · ${fmtPrice(o.plan.stop_loss, p)} · ${fmtPrice(o.plan.targets[0].price, p)}`
                          : "hidden (unvalidated)") : "—"}
                      </TD>
                      <TD className="max-w-[22rem] text-xs text-muted-foreground">{i.primary.action === "EXIT" ? i.primary.headline : o?.next_action ?? i.primary.headline}</TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </QueryState>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const instruments = useInstruments();
  const quotes = useQuotes();
  const preds = usePredictions({ limit: 6 });
  const coverage = useCoverage();
  const models = useModels();
  const analyses = useAnalyses(5);

  return (
    <>
      <PageHeader title="Overview" description="Live quotes, structure bias, recent predictions and data health for the tracked instruments. Every number comes from the backend; nothing is simulated." />

      <QueryState query={instruments} skeleton={<div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-36" />)}</div>}>
        {(list) => (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((i) => (
              <QuoteCard key={i.id} inst={i} quote={quotes.data?.find((q) => q.symbol === i.canonical_symbol)} />
            ))}
          </div>
        )}
      </QueryState>

      <div className="mt-4"><DecisionsNow /></div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Recent predictions</CardTitle>
            <Link href="/predictions" className="text-xs text-primary hover:underline">View all</Link>
          </CardHeader>
          <CardContent className="p-0">
            <QueryState
              query={preds}
              isEmpty={(d) => d.items.length === 0}
              empty={<div className="p-4"><EmptyState title="No predictions yet" hint="Open Chart Analysis, pick an instrument and run an analysis. Results will appear here." action={<Link className="text-xs text-primary hover:underline" href="/chart">Go to Chart Analysis</Link>} /></div>}
            >
              {(d) => (
                <Table>
                  <THead><TR><TH>Instrument</TH><TH>TF</TH><TH>Decision</TH><TH>R:R</TH><TH>As of</TH><TH><span className="sr-only">Details</span></TH></TR></THead>
                  <TBody>
                    {d.items.map((p) => (
                      <TR key={p.id}>
                        <TD className="font-medium">{p.symbol}</TD>
                        <TD>{p.timeframe}</TD>
                        <TD>{p.call ? <CallBadge call={p.call} className="text-[10px]" /> : <DecisionBadge decision={p.decision} />}</TD>
                        <TD className="num">{p.call?.levels?.risk_reward ? `1:${fmtNum(p.call.levels.risk_reward, 1)}` : "—"}</TD>
                        <TD className="num text-muted-foreground">{fmtDate(p.as_of_ts)}</TD>
                        <TD><Link href={`/predictions/${p.id}`} className="text-xs text-primary hover:underline">Details</Link></TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </QueryState>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Model status</CardTitle><Link href="/models" className="text-xs text-primary hover:underline">Manage</Link></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <QueryState query={models} isEmpty={(d) => d.items.length === 0} empty={<p className="text-muted-foreground">No models trained. Predictions use price-action evidence and historical analogues only.</p>}>
              {(d) => (
                <>
                  {d.items.slice(0, 4).map((m) => (
                    <div key={m.id} className="flex items-center justify-between gap-2">
                      <span className="truncate">{m.name}</span>
                      <Badge variant={m.validation_status === "passed_minimum_checks" ? "buy" : "wait"}>{m.validation_status.replace(/_/g, " ")}</Badge>
                    </div>
                  ))}
                </>
              )}
            </QueryState>
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Market direction (1H structure)</CardTitle></CardHeader>
          <CardContent className="p-0">
            <QueryState query={instruments}>{(list) => <Table><TBody>{list.map((i) => <DirectionRow key={i.id} inst={i} />)}</TBody></Table>}</QueryState>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Data coverage</CardTitle><Link href="/data-sources" className="text-xs text-primary hover:underline">Details</Link></CardHeader>
          <CardContent className="p-0">
            <QueryState query={coverage} isEmpty={(d) => d.length === 0} empty={<div className="p-4"><EmptyState title="No candles stored" hint="Sync data from Data Sources or run an analysis with auto-sync enabled." /></div>}>
              {(d) => (
                <Table>
                  <THead><TR><TH>Symbol</TH><TH>TF</TH><TH className="text-right">Candles</TH><TH className="text-right">Gaps</TH></TR></THead>
                  <TBody>
                    {d.slice(0, 8).map((c) => (
                      <TR key={`${c.instrument}${c.timeframe}`}><TD>{c.instrument}</TD><TD>{c.timeframe}</TD><TD className="num text-right">{c.candle_count}</TD><TD className="num text-right">{c.gap_count}</TD></TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </QueryState>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Recent analysis jobs</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {analyses.isError ? <ErrorState error={analyses.error} onRetry={() => void analyses.refetch()} /> : null}
            {analyses.data?.items.length === 0 && <p className="text-muted-foreground">No analyses run yet.</p>}
            {analyses.data?.items.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-2">
                <span>{a.symbol} · {a.timeframe}</span>
                <span className="flex items-center gap-2"><JobBadge status={a.status} /><span className="text-xs text-muted-foreground">{timeAgo(a.created_at)}</span></span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4"><AnalysisOnlyNotice /></div>
    </>
  );
}

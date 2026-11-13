"use client";

import { Briefcase, Coins, LineChart, Zap } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/misc";
import { CallBadge } from "@/components/domain/call";
import { ActionBadge } from "@/components/domain/engine";
import { DecisionBadge, EmptyState, PageHeader, QueryState } from "@/components/domain/common";
import { AreaChart, Donut, KpiTile } from "@/components/domain/overview";
import { AnalysisOnlyNotice } from "@/components/domain/decision";
import { useCandles, useEngineSignals, useEngineSummary, useHealth, useInstruments, useModels, usePaperSummary, usePredictions, useQuotes } from "@/lib/hooks";
import type { Instrument, Quote } from "@/lib/types";
import { useSettings } from "@/lib/store";
import { cn, fmtDate, fmtNum, fmtPrice, fmtSignedR, timeAgo } from "@/lib/utils";

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

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
};

const ACTION_COLORS = { buy: "#34d07f", sell: "#f87171", wait: "#f6b03e", none: "#4b4b63" };

const STRATEGY_ROWS: [string, string][] = [["trend_pullback", "Trend-following pullback"], ["breakout_retest", "Breakout and retest"],
  ["momentum_continuation", "Momentum continuation"], ["range_reversion", "Range mean reversion"], ["sweep_reversal", "Liquidity-sweep reversal"],
  ["volatility_expansion", "Volatility expansion"]];

function HealthRow({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-2"><span className={cn("h-2 w-2 rounded-full", ok ? "bg-bull" : "bg-warn")} />{label}</span>
      <span className="truncate text-right text-xs text-muted-foreground">{value}</span>
    </div>
  );
}

export default function DashboardPage() {
  const instruments = useInstruments();
  const quotes = useQuotes();
  const preds = usePredictions({ limit: 6 });
  const models = useModels();
  const engine = useEngineSummary();
  const paper = usePaperSummary();
  const gold = useCandles("XAUUSD", "1H", 48);
  const health = useHealth();
  const recent = useEngineSignals();

  const tfs = (engine.data?.items ?? []).flatMap((i) => i.tfs ?? []);
  const count = (f: (a: string) => boolean) => tfs.filter((t) => f(t.action)).length;
  const buy = count((a) => a === "BUY");
  const sell = count((a) => a === "SELL");
  const wait = count((a) => a.startsWith("WAIT"));
  const none = count((a) => a === "NO TRADE");
  const closes = (gold.data?.candles ?? []).map((c) => c.close);
  const goldQuote = quotes.data?.find((q) => q.symbol === "XAUUSD");
  const goldPx = goldQuote?.status === "ok" ? goldQuote.price : closes[closes.length - 1];
  const goldDelta = closes.length > 24 && goldPx ? ((goldPx - closes[closes.length - 25]) / closes[closes.length - 25]) * 100 : null;
  const fwd = paper.data?.forward;
  const curve = (fwd?.equity_curve ?? []).map((x) => ({ t: x.t, v: x.r }));
  const openTrades = paper.data?.open ?? [];
  const openR = openTrades.reduce((s, t) => s + (t.unrealized_r ?? 0), 0);
  const latestData = (engine.data?.items ?? []).map((i) => i.data_time).filter(Boolean).sort().pop() ?? null;

  return (
    <>
      <PageHeader title="Overview" description={`${greeting()}. Here is what the strategy engine and the paper test show right now. Every number comes from the backend; nothing is simulated.`} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="kpis">
        <KpiTile icon={Coins} tone="violet" label="Gold (XAUUSD)" value={fmtPrice(goldPx, 2)} delta={goldDelta} sub=" over 24 h" spark={closes.slice(-48)} testId="kpi-gold" />
        <KpiTile icon={Zap} tone="green" label="Signals now" value={engine.data ? `${buy + sell} BUY/SELL` : "…"}
          sub={engine.data ? `${wait} waiting for entry · ${none} no trade` : "loading the engine"} testId="kpi-signals" />
        <KpiTile icon={LineChart} tone="blue" label="Forward test (paper)" value={fwd ? fmtSignedR(fwd.total_r, 1) : "—"}
          sub={fwd ? `${fwd.n_trades} closed · ${fmtSignedR(fwd.expectancy_r, 2)} per trade` : "loading"} spark={curve.slice(-60).map((x) => x.v)} testId="kpi-forward" />
        <KpiTile icon={Briefcase} tone="orange" label="Open paper trades" value={String(openTrades.length)}
          sub={openTrades.length ? `${fmtSignedR(openR, 1)} unrealised in total` : "none open"} testId="kpi-open" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Forward-test equity (cumulative R)</CardTitle>
            <Link href="/paper" className="text-xs text-primary hover:underline">Paper Trading</Link>
          </CardHeader>
          <CardContent>
            <div className="mb-2 flex flex-wrap items-baseline gap-2">
              <span className="num text-2xl font-bold">{fwd ? fmtSignedR(fwd.total_r, 2) : "—"}</span>
              <span className="text-xs text-muted-foreground">{fwd ? `${fwd.n_trades} closed paper trades, net of the spread: the v1 rules, not a validated strategy` : ""}</span>
            </div>
            <QueryState query={paper} skeleton={<Skeleton className="h-52 w-full" />}>{() => <AreaChart values={curve} label="Forward-test equity" unit="R" />}</QueryState>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Signals by action</CardTitle><span className="text-xs text-muted-foreground">every instrument × timeframe</span></CardHeader>
          <CardContent data-testid="signals-donut">
            <QueryState query={engine} skeleton={<Skeleton className="h-40 w-full" />}>
              {() => (
                <Donut label="Signals by action" center={tfs.length ? `${Math.round(((buy + sell + wait) / tfs.length) * 100)}%` : "—"} sub="with a plan"
                  segments={[{ label: "BUY", value: buy, color: ACTION_COLORS.buy }, { label: "SELL", value: sell, color: ACTION_COLORS.sell },
                    { label: "WAIT FOR ENTRY", value: wait, color: ACTION_COLORS.wait }, { label: "NO TRADE", value: none, color: ACTION_COLORS.none }]} />
              )}
            </QueryState>
          </CardContent>
        </Card>
      </div>

      <div className="mt-4"><DecisionsNow /></div>

      <div className="mt-4">
        <QueryState query={instruments} skeleton={<div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-36" />)}</div>}>
          {(list) => (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {list.map((i) => (
                <QuoteCard key={i.id} inst={i} quote={quotes.data?.find((q) => q.symbol === i.canonical_symbol)} />
              ))}
            </div>
          )}
        </QueryState>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader><CardTitle>Recent signals</CardTitle><Link href="/signals" className="text-xs text-primary hover:underline">All signals</Link></CardHeader>
          <CardContent className="space-y-2" data-testid="recent-signals">
            {(recent.data?.items ?? []).slice(0, 5).map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-2 rounded-lg border border-border/60 px-3 py-2 text-sm">
                <span className="min-w-0">
                  <span className="font-semibold">{r.symbol}</span> <span className="text-muted-foreground">{r.timeframe}</span>{" "}
                  <span className={r.direction === "BUY" ? "text-bull" : "text-bear"}>{r.direction}</span>
                  <span className="block truncate text-[11px] text-muted-foreground">{r.strategy_name ?? r.strategy} · {timeAgo(r.detected_at)}</span>
                </span>
                <Badge variant={r.status.includes("TP") ? "buy" : r.status.includes("STOP") || r.status === "INVALIDATED" ? "sell" : "info"} className="shrink-0 text-[10px]">{r.status}</Badge>
              </div>
            ))}
            {recent.data && recent.data.items.length === 0 && <p className="text-sm text-muted-foreground">No signals recorded yet.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Strategies</CardTitle><span className="text-xs text-muted-foreground">research status</span></CardHeader>
          <CardContent className="space-y-2" data-testid="strategy-list">
            {STRATEGY_ROWS.map(([key, name]) => {
              const live = (engine.data?.items ?? []).filter((i) => i.opportunity?.strategy === key).length;
              return (
                <div key={key} className="flex items-center justify-between gap-2 text-sm">
                  <span className="min-w-0 truncate">{name}</span>
                  <span className="flex shrink-0 items-center gap-2">
                    {live > 0 && <span className="text-[11px] text-muted-foreground">{live} live</span>}
                    <Badge variant="wait" className="text-[10px]">not validated</Badge>
                  </span>
                </div>
              );
            })}
            <p className="pt-1 text-[11px] text-muted-foreground">No strategy has passed research validation: every plan is hypothetical.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>System health</CardTitle><Link href="/data-sources" className="text-xs text-primary hover:underline">Data sources</Link></CardHeader>
          <CardContent className="space-y-2 text-sm" data-testid="system-health">
            <HealthRow label="Backend" ok={health.data?.status === "ok"} value={health.data ? health.data.status : "…"} />
            <HealthRow label="Market data" ok={!!latestData} value={latestData ? `latest candle ${timeAgo(latestData)}` : "…"} />
            <HealthRow label="Paper cycle" ok={!!paper.data?.worker.enabled && !paper.data?.worker.last_error}
              value={paper.data ? (paper.data.worker.enabled ? `every ${paper.data.worker.interval_s}s, last ${timeAgo(paper.data.worker.last_cycle_at)}` : "off") : "…"} />
            <HealthRow label="Instruments analysed" ok={(engine.data?.items ?? []).every((i) => i.status === "ok")}
              value={engine.data ? `${engine.data.items.filter((i) => i.status === "ok").length} of ${engine.data.items.length}` : "…"} />
            <HealthRow label="News filter" ok={false} value="not available (not filtered)" />
          </CardContent>
        </Card>
      </div>

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

      <div className="mt-4"><AnalysisOnlyNotice /></div>
    </>
  );
}

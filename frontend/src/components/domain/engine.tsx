"use client";

// Displays strategy engine v2 output (backend app/strategy_engine). Nothing here decides: every action, price and reason comes from
// the API. Unvalidated plans are always labelled; with experimental analysis mode off their prices are hidden.

import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { EmptyState, QueryState } from "@/components/domain/common";
import { ConfirmationChips, ConfirmationDetail } from "@/components/domain/confirmations";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { EngineAction, EngineItem, EnginePlan, EngineTimeframe, EngineTradeRow, SignalRecord } from "@/lib/engine-types";
import { useEngine, useEngineSignals, useEngineSummary } from "@/lib/hooks";
import { useSettings } from "@/lib/store";
import { cn, fmtDate, fmtNum, fmtPrice, fmtSignedR, timeAgo } from "@/lib/utils";

const TONE: Record<EngineAction, { box: string; text: string; badge: "buy" | "sell" | "wait" | "neutral" }> = {
  BUY: { box: "border-bull/50 bg-bull/10", text: "text-bull", badge: "buy" },
  SELL: { box: "border-bear/50 bg-bear/10", text: "text-bear", badge: "sell" },
  "WAIT FOR BUY": { box: "border-warn/40 bg-warn/10", text: "text-warn", badge: "wait" },
  "WAIT FOR SELL": { box: "border-warn/40 bg-warn/10", text: "text-warn", badge: "wait" },
  EXIT: { box: "border-bear/60 bg-bear/10", text: "text-bear", badge: "sell" },
  "NO TRADE": { box: "border-border bg-muted/50", text: "text-muted-foreground", badge: "neutral" },
};

export function ActionBadge({ action, className }: { action: EngineAction; className?: string }) {
  return <Badge variant={TONE[action].badge} className={cn("whitespace-nowrap font-bold", className)} data-testid="action-badge">{action}</Badge>;
}

const MODE = { market: "at market", limit: "limit order", stop: "stop order" } as const;

function Level({ label, value, sub, tone, testId }: { label: string; value: string; sub?: string; tone?: string; testId?: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border/60 bg-surface px-3 py-2" data-testid={testId}>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={cn("num text-base font-bold sm:text-lg", tone)}>{value}</div>
      {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

/** Entry, stop-loss and TP1-TP3 as large numbers, then reward:risk, costs, entry status and expiry. */
export function PlanGrid({ plan, p, hidden }: { plan: EnginePlan; p: number; hidden: boolean }) {
  if (hidden) {
    return (
      <p className="rounded-lg border border-dashed p-3 text-xs text-muted-foreground" data-testid="plan-hidden">
        Entry, stop-loss and targets of this unvalidated plan are hidden. Tick “Show hypothetical trade plans” above to see them.
      </p>
    );
  }
  const zone = plan.entry_zone && plan.entry_zone.length === 2 ? `zone ${fmtPrice(plan.entry_zone[0], p)}–${fmtPrice(plan.entry_zone[1], p)}` : MODE[plan.entry_mode];
  return (
    <div className="space-y-2" data-testid="plan-grid">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <Level label="Entry" value={fmtPrice(plan.entry, p)} sub={zone} testId="lv-entry" />
        <Level label="Stop loss" value={fmtPrice(plan.stop_loss, p)} sub={`risk ${fmtPrice(plan.risk, p)} (${fmtNum(plan.risk_atr, 1)} ATR)`} tone="text-bear" testId="lv-sl" />
        {plan.targets.map((t) => (
          <Level key={t.label} label={t.label} value={fmtPrice(t.price, p)} sub={`${fmtNum(t.rr, 2)}R · ${t.basis}`} tone="text-bull" testId={`lv-${t.label.toLowerCase()}`} />
        ))}
      </div>
      <p className="num text-xs text-muted-foreground" data-testid="plan-facts">
        Risk/reward 1:{fmtNum(plan.risk_reward, 2)} (TP1), 1:{fmtNum(plan.targets[1]?.rr, 2)} (TP2), 1:{fmtNum(plan.targets[2]?.rr, 2)} (TP3) ·
        spread {fmtPrice(plan.spread, p)} ({fmtNum(plan.cost_r, 2)}R) · status <strong className="text-foreground">{plan.entry_status}</strong> ·
        signal {fmtDate(plan.signal_time)} · expires {fmtDate(plan.expires_at)}
      </p>
    </div>
  );
}

function TradeBlock({ trades, p }: { trades: EngineTradeRow[]; p: number }) {
  if (!trades.length) return null;
  return (
    <div className="rounded-lg border border-border/60 p-3" data-testid="paper-trades">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Paper trades on this instrument (forward test of the v1 rules: separate from the signal above)
      </div>
      <ul className="space-y-1 text-xs">
        {trades.map((t) => (
          <li key={t.id} className="num flex flex-wrap items-baseline gap-x-2">
            <span className="font-semibold">{t.timeframe}</span>
            <span className={t.direction === "BUY" ? "text-bull" : "text-bear"}>{t.direction}</span>
            <span>entry {fmtPrice(t.fill_price ?? t.entry_price, p)} · now {fmtPrice(t.last_price, p)} · SL {fmtPrice(t.stop_loss, p)} · TP {fmtPrice(t.take_profit, p)}</span>
            {t.unrealized_r != null && <span className={t.unrealized_r >= 0 ? "text-bull" : "text-bear"}>{fmtSignedR(t.unrealized_r)}</span>}
            {t.management && (
              <span className={cn("font-semibold", t.management.action === "EXIT" ? "text-bear" : "text-primary")} title={t.management.reason}>
                {t.management.action}: {t.management.reason}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function OpportunityBody({ o, p, hidden }: { o: NonNullable<EngineItem["opportunity"]>; p: number; hidden: boolean }) {
  const d = o.direction === "BUY" ? "BUY" : "SELL";
  return (
    <div className="space-y-3">
      {o.plan && <PlanGrid plan={o.plan} p={p} hidden={hidden} />}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Why {d.toLowerCase()}?</div>
          <ul className="list-disc space-y-0.5 pl-4 text-xs" data-testid="why">{o.why.slice(0, 4).map((w, i) => <li key={i}>{w}</li>)}</ul>
          {o.agreeing.length > 0 && <p className="mt-1 text-[11px] text-muted-foreground">Also seen by: {o.agreeing.join(", ")}</p>}
        </div>
        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">What invalidates it?</div>
          <p className="text-xs" data-testid="invalidation">{o.plan ? `${o.plan.invalidation_text} (stop ${hidden ? "hidden" : fmtPrice(o.plan.stop_loss, p)})` : "—"}</p>
        </div>
        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Next action</div>
          <p className="text-xs font-medium" data-testid="next-action">{hidden && o.plan ? o.headline : o.next_action}</p>
        </div>
      </div>
      {o.missing.length > 0 && (
        <p className="text-xs text-warn" data-testid="missing">Missing: {o.missing.join("; ")}</p>
      )}
      {o.conflict && <p className="text-xs text-warn">Conflict: {o.conflict.buy} (BUY) vs {o.conflict.sell} (SELL): {o.conflict.resolution}.</p>}
    </div>
  );
}

/** One instrument: the primary action and its prices, readable in three seconds; the full analysis on demand. */
export function SignalCard({ item }: { item: EngineItem }) {
  const experimental = useSettings((s) => s.experimentalMode);
  const [open, setOpen] = useState(false);
  const [evidence, setEvidence] = useState(false);
  const p = item.price_precision ?? 2;
  const pr = item.primary;
  const o = item.opportunity;
  const shown: EngineAction = pr.action === "EXIT" ? "EXIT" : pr.action;
  const hidden = !experimental && !!o && o.research_status !== "VALIDATED";
  return (
    <section className={cn("rounded-2xl border-2 bg-card p-4 shadow-card sm:p-5", TONE[shown].box, open && "xl:col-span-2")} data-testid={`signal-${item.symbol}`}
      aria-label={`${item.symbol}: ${pr.action}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-lg font-bold tracking-tight">{item.symbol}</div>
          <div className="text-xs text-muted-foreground">{item.name}</div>
        </div>
        <div className="text-right">
          <div className="num text-lg font-semibold">{fmtPrice(item.price_now, p)}</div>
          <div className="text-[11px] text-muted-foreground">{item.price_source} · data {timeAgo(item.data_time)}{item.session ? ` · ${item.session.label}` : ""}</div>
        </div>
      </div>

      {pr.action === "EXIT" && pr.exit && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-bear/40 bg-bear/10 p-3 text-sm" role="alert" data-testid="exit-banner">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-bear" aria-hidden />
          <div>
            <div className="font-bold text-bear">EXIT the tracked paper {pr.exit.direction} trade ({pr.exit.timeframe})</div>
            <div className="text-xs">{pr.exit.reason}</div>
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={cn("text-3xl font-black tracking-tight sm:text-4xl", TONE[o ? o.action : pr.action === "EXIT" ? "NO TRADE" : pr.action].text)}
          data-testid="primary-action">
          {o ? o.action : pr.action === "EXIT" ? "NO TRADE" : pr.action}
        </span>
        {o && (
          <span className="text-sm font-medium" data-testid="setup-line">
            {o.strategy_name} · {o.timeframe} · {o.regime.name}
          </span>
        )}
      </div>
      {pr.action === "EXIT" && <div className="text-[11px] text-muted-foreground">New opportunity (independent of the paper trade above)</div>}

      {o ? (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge variant={o.research_status === "VALIDATED" ? "buy" : "wait"} data-testid="plan-label">{o.plan_label}</Badge>
            <span className="text-xs text-muted-foreground" data-testid="research-status">Research: {o.research_status}</span>
            <span className="text-xs text-muted-foreground">Technical: {o.technical_status}</span>
          </div>
          <div className="mt-3"><OpportunityBody o={o} p={p} hidden={hidden} /></div>
          {o.confirmations && o.confirmations.length > 0 && (
            <div className="mt-3 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <ConfirmationChips items={o.confirmations} />
                <button className="text-xs font-medium text-primary hover:underline" onClick={() => setEvidence((v) => !v)} aria-expanded={evidence}
                  data-testid="toggle-evidence">
                  {evidence ? "Hide evidence" : "Evidence"}
                </button>
              </div>
              {evidence && <ConfirmationDetail items={o.confirmations} volume={o.volume} vsa={o.vsa} />}
            </div>
          )}
        </>
      ) : (
        <div className="mt-2 space-y-1 text-sm" data-testid="no-trade">
          <p>{pr.headline}</p>
          {pr.why && pr.why.length > 0 && <ul className="list-disc pl-4 text-xs text-muted-foreground">{pr.why.map((w, i) => <li key={i}>{w}</li>)}</ul>}
        </div>
      )}

      <div className="mt-3"><TradeBlock trades={item.trades} p={p} /></div>

      <button className="mt-3 flex items-center gap-1 text-xs font-medium text-primary hover:underline" onClick={() => setOpen((v) => !v)}
        aria-expanded={open} data-testid="toggle-detail">
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />} All timeframes and strategies
      </button>
      {open && <EngineDetailPanel symbol={item.symbol} precision={p} hidden={!experimental} />}
    </section>
  );
}

function StrategyList({ tf }: { tf: EngineTimeframe }) {
  return (
    <ul className="space-y-1 text-xs" data-testid={`strategies-${tf.timeframe}`}>
      {tf.candidates.filter((c) => c.status !== "not run").map((c) => (
        <li key={`${c.strategy}-${c.side}`} className="flex flex-wrap gap-x-2">
          <span className="font-medium">{c.name} {c.side}</span>
          <span className={cn("uppercase", c.status === "ready" || c.plan?.entry_status === "READY" ? "text-bull" : c.status === "pending" ? "text-warn" : "text-muted-foreground")}>
            {c.status === "pending" && c.plan?.entry_status === "READY" ? "ready (price at the entry)" : c.status}
          </span>
          <span className="text-muted-foreground">{c.missing[0] ?? c.reasons[c.reasons.length - 1] ?? ""}</span>
        </li>
      ))}
      <li className="text-muted-foreground">Not run in a {tf.regime.name.toLowerCase()} regime: {tf.candidates.filter((c) => c.status === "not run" && c.direction > 0).map((c) => c.name).join(", ") || "none"}</li>
    </ul>
  );
}

export function EngineDetailPanel({ symbol, precision, hidden }: { symbol: string; precision: number; hidden: boolean }) {
  const q = useEngine(symbol);
  const [sel, setSel] = useState<string | null>(null);
  return (
    <div className="mt-2" data-testid="engine-detail">
      <QueryState query={q} skeleton={<Skeleton className="h-40 w-full" />}>
        {(d) => {
          const cur = d.timeframes.find((t) => t.timeframe === sel) ?? null;
          return (
            <div className="space-y-3">
              <Table>
                <THead><TR><TH>TF</TH><TH>Regime</TH><TH>Action</TH><TH>Strategy</TH><TH>Entry · SL · TP1</TH><TH>Status</TH></TR></THead>
                <TBody>
                  {d.timeframes.map((t) => (
                    <TR key={t.timeframe} className={cn("cursor-pointer", sel === t.timeframe && "bg-primary/5")} onClick={() => setSel(t.timeframe)}
                      data-testid={`etf-${t.timeframe}`}>
                      <TD className="num font-medium">{t.timeframe}</TD>
                      <TD className="text-xs" title={t.regime.reason}>{t.regime.name}</TD>
                      <TD><ActionBadge action={t.action} className="text-[10px]" /></TD>
                      <TD className="text-xs">{t.strategy_name ?? "—"}</TD>
                      <TD className="num whitespace-nowrap text-xs">
                        {t.plan && !hidden ? `${fmtPrice(t.plan.entry, precision)} · ${fmtPrice(t.plan.stop_loss, precision)} · ${fmtPrice(t.plan.targets[0].price, precision)}` : t.plan ? "hidden" : "—"}
                      </TD>
                      <TD className="max-w-[16rem] text-xs text-muted-foreground">{t.plan ? t.plan.entry_status : t.missing[0] ?? t.headline}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              {cur ? (
                <div className="rounded-lg border p-3">
                  <div className="mb-1 text-sm font-semibold">{cur.timeframe}: {cur.headline}</div>
                  <p className="mb-2 text-xs text-muted-foreground">Regime: {cur.regime.reason}{cur.context_regime ? ` · context ${cur.context_tf}: ${cur.context_regime.name}` : ""}</p>
                  <StrategyList tf={cur} />
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Click a timeframe to see every strategy&apos;s verdict on it.</p>
              )}
              <p className="text-[11px] text-muted-foreground">{d.research.note} {d.news.note}</p>
            </div>
          );
        }}
      </QueryState>
    </div>
  );
}

/** Lifecycle of recorded signals (hypothetical tracking on 1-minute candles, not paper trades). */
export function SignalHistory({ precisions }: { precisions: Record<string, number> }) {
  const q = useEngineSignals();
  return (
    <Card data-testid="signal-history">
      <CardHeader>
        <CardTitle>Signal history and lifecycle</CardTitle>
        <span className="text-xs text-muted-foreground">each signal recorded once and followed on 1-minute candles · hypothetical, not paper trades</span>
      </CardHeader>
      <CardContent className="p-0">
        <QueryState query={q} isEmpty={(d) => d.items.length === 0}
          empty={<div className="p-4"><EmptyState title="No signals recorded yet" hint="The engine records each qualified plan the first time it appears." /></div>}>
          {(d) => (
            <Table>
              <THead><TR><TH>Signal</TH><TH>Entry</TH><TH>SL</TH><TH>TP1 / TP2 / TP3</TH><TH>Status</TH><TH>Detected</TH></TR></THead>
              <TBody>
                {d.items.map((r: SignalRecord) => {
                  const p = precisions[r.symbol] ?? 2;
                  const last = r.history[r.history.length - 1];
                  return (
                    <TR key={r.id} data-testid={`rec-${r.id}`}>
                      <TD className="whitespace-nowrap text-xs"><span className="font-semibold">{r.symbol}</span> {r.timeframe}{" "}
                        <span className={r.direction === "BUY" ? "text-bull" : "text-bear"}>{r.direction}</span>
                        <span className="block text-[11px] text-muted-foreground">{r.strategy_name ?? r.strategy}</span></TD>
                      <TD className="num text-xs">{fmtPrice(r.entry, p)} <span className="text-muted-foreground">{r.entry_mode}</span></TD>
                      <TD className="num text-xs">{fmtPrice(r.stop_loss, p)}</TD>
                      <TD className="num whitespace-nowrap text-xs">{fmtPrice(r.tp1, p)} / {fmtPrice(r.tp2, p)} / {fmtPrice(r.tp3, p)}</TD>
                      <TD className="text-xs font-semibold" title={last?.note}>{r.status}</TD>
                      <TD className="whitespace-nowrap text-xs text-muted-foreground">{timeAgo(r.detected_at)}</TD>
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


/** The strategy engine's current action for one instrument and timeframe: shown on pages that run other analyses, so every page agrees. */
export function EngineNowStrip({ symbol, timeframe }: { symbol: string; timeframe: string }) {
  const q = useEngine(symbol);
  const experimental = useSettings((s) => s.experimentalMode);
  const t = q.data?.timeframes.find((x) => x.timeframe === timeframe) ?? null;
  const p = q.data?.price_precision ?? 2;
  return (
    <div className="rounded-xl border border-primary/30 bg-primary/5 p-3 text-sm" data-testid="engine-now">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Strategy engine now ({symbol} {timeframe})</div>
      {q.isLoading ? <span className="text-xs text-muted-foreground">loading…</span> : q.isError ? (
        <span className="text-xs text-muted-foreground">The strategy engine is not reachable right now.</span>
      ) : !t ? (
        <span className="text-xs text-muted-foreground">The strategy engine does not analyse {timeframe}; see the Signals page for its timeframes.</span>
      ) : (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <ActionBadge action={t.action} />
          <span className="text-xs">{t.strategy_name ?? t.headline.replace(/^NO TRADE: /, "")}</span>
          {t.plan && (experimental || t.research_status === "VALIDATED") && (
            <span className="num text-xs text-muted-foreground">entry {fmtPrice(t.plan.entry, p)} · SL {fmtPrice(t.plan.stop_loss, p)} · TP1 {fmtPrice(t.plan.targets[0].price, p)}</span>
          )}
          {t.plan && <Badge variant="wait" className="text-[10px]">unvalidated</Badge>}
          <a href="/signals" className="text-xs font-medium text-primary hover:underline">Signals</a>
        </div>
      )}
    </div>
  );
}

/** Each instrument's primary action, one line: the shared decision shown above other analyses. */
export function EngineSummaryStrip() {
  const q = useEngineSummary();
  if (!q.data) return null;
  return (
    <div className="mb-4 rounded-xl border border-primary/30 bg-primary/5 p-3" data-testid="engine-strip">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Strategy engine now (the platform&apos;s decision; this page is the older opportunity scanner, shown for comparison)
      </div>
      <div className="flex flex-wrap gap-2">
        {q.data.items.map((i) => (
          <a key={i.symbol} href="/signals" className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-card px-2 py-1 text-xs hover:border-primary/50">
            <span className="font-semibold">{i.symbol}</span>
            <ActionBadge action={i.primary.action === "EXIT" ? "EXIT" : i.opportunity?.action ?? i.primary.action} className="px-1.5 text-[10px]" />
            {i.opportunity && <span className="text-muted-foreground">{i.opportunity.timeframe}</span>}
          </a>
        ))}
      </div>
    </div>
  );
}

const CATEGORIES: [string, string, string][] = [
  ["Technical setup", "Technical: QUALIFIED / DEVELOPING", "A strategy's chart conditions as measured now. Says nothing about profitability."],
  ["Validated strategy", "Research: VALIDATED", "Passed the pre-registered historical test, the sealed final test and a paper forward test. None today."],
  ["Hypothetical trade plan", "UNVALIDATED — HYPOTHETICAL TRADE PLAN", "Entry, stop-loss and targets of an unvalidated setup: analysis, not a recommendation."],
  ["Paper trade", "Paper trades block", "A simulated order of the forward test (no money). Never a signal for you to copy."],
  ["Broker trade", "none", "This platform never sends orders to a broker. Any real trade is your own decision."],
];

/** What each label means: the five categories a customer must never confuse. */
export function CategoryLegend() {
  return (
    <details className="mb-4 rounded-xl border border-border/60 bg-card p-3 text-sm" data-testid="category-legend">
      <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">What the labels mean (setup, validated strategy, hypothetical plan, paper trade, broker trade)</summary>
      <dl className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-5">
        {CATEGORIES.map(([title, label, text]) => (
          <div key={title} className="rounded-lg border border-border/60 p-2">
            <dt className="text-xs font-semibold">{title}</dt>
            <dd className="text-[11px] text-primary">{label}</dd>
            <dd className="mt-1 text-[11px] text-muted-foreground">{text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

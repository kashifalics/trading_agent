"use client";

import { CheckCircle2, CircleSlash, Info, XCircle } from "lucide-react";
import { useMemo } from "react";
import { CandleChart } from "@/components/charts/candle-chart";
import { COLORS, type ChartLine, type ChartZone } from "@/components/charts/overlays";
import { CallBadge, CallCard } from "@/components/domain/call";
import { EmptyState, ErrorState } from "@/components/domain/common";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/form";
import { Meter, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useSignalCandles } from "@/lib/hooks";
import { DEFAULT_CONTRACT_SIZE, positionSize } from "@/lib/position-size";
import type { Overall, SignalAnalysis, SignalState, SignalsSummaryItem, TimeframePlan, TimeframeRow } from "@/lib/signal-types";
import { useSettings } from "@/lib/store";
import { cn, fmtNum, fmtPct, fmtPrice } from "@/lib/utils";

export const STATE_LABEL: Record<SignalState, string> = {
  ENTRY_READY: "Entry ready",
  WAITING_FOR_CONFIRMATION: "Waiting for confirmation",
  SETUP_DEVELOPING: "Setup developing",
  WATCHLIST: "Watchlist",
  NO_SETUP: "No setup",
  TRADE_INVALIDATED: "Invalidated",
  TRADE_EXPIRED: "Expired",
};
const STATE_VARIANT: Record<SignalState, "buy" | "sell" | "wait" | "neutral" | "info"> = {
  ENTRY_READY: "buy", WAITING_FOR_CONFIRMATION: "wait", SETUP_DEVELOPING: "info", WATCHLIST: "neutral", NO_SETUP: "neutral",
  TRADE_INVALIDATED: "sell", TRADE_EXPIRED: "neutral",
};
const ACTIONABLE: SignalState[] = ["ENTRY_READY", "WAITING_FOR_CONFIRMATION", "SETUP_DEVELOPING"];
export const isActionable = (s: SignalState) => ACTIONABLE.includes(s);
const words = (s?: string | null) => (s ?? "").replace(/_/g, " ");

export function StateBadge({ state }: { state: SignalState }) {
  return <Badge variant={STATE_VARIANT[state]} data-testid="state-badge">{STATE_LABEL[state]}</Badge>;
}

export function SideBadge({ side }: { side: "BUY" | "SELL" | null | undefined }) {
  if (!side) return <span className="text-muted-foreground">—</span>;
  return <Badge variant={side === "BUY" ? "buy" : "sell"} className="num px-2.5 font-semibold tracking-wider">{side}</Badge>;
}

function biasTone(label?: string) {
  return label?.includes("ullish") ? "text-bull" : label?.includes("earish") ? "text-bear" : "text-muted-foreground";
}

export function ScoreMeter({ score, grade }: { score: number | null; grade?: "A" | "B" | null }) {
  if (score === null) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="min-w-[90px]">
      <div className="num flex items-baseline gap-1 text-sm font-semibold">
        {score}<span className="text-xs font-normal text-muted-foreground">/100</span>
        {grade && <Badge variant={grade === "A" ? "buy" : "info"} className="ml-1 px-1.5 py-0 text-[10px]">{grade}</Badge>}
      </div>
      <Meter value={score / 100} className="mt-1" />
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ instrument tabs
export function InstrumentTabs({ items, value, onChange }: { items: SignalsSummaryItem[]; value: string | null; onChange: (s: string) => void }) {
  return (
    <div role="tablist" aria-label="Instrument" className="flex flex-wrap gap-2">
      {items.map((i) => {
        const best = i.best;
        return (
          <button key={i.symbol} role="tab" aria-selected={value === i.symbol} onClick={() => onChange(i.symbol)} data-testid={`tab-${i.symbol}`}
            className={cn("flex min-w-[150px] flex-col items-start rounded-2xl border px-4 py-2.5 text-left shadow-card transition-colors",
              value === i.symbol ? "border-primary/50 bg-primary/5" : "border-border/60 bg-card hover:bg-muted/50")}>
            <span className="text-sm font-semibold">{i.symbol}</span>
            {i.call ? (
              <span className="flex flex-col items-start gap-1">
                <CallBadge call={i.call} className="text-[10px]" />
                <span className="text-[11px] text-muted-foreground">{i.call.timeframe ?? (i.status !== "ok" ? "no data" : "")}{i.call.direction !== "NONE" ? ` · ${i.call.direction}` : ""}</span>
              </span>
            ) : i.status !== "ok" ? (
              <span className="text-xs text-muted-foreground">{i.status === "failed" ? "analysis failed" : "no data yet"}</span>
            ) : best ? (
              <span className="flex items-center gap-1.5 text-xs">
                <span className={best.direction === "BUY" ? "text-bull" : "text-bear"}>{best.direction}</span>
                <span className="text-muted-foreground">{best.timeframe} · {best.score}/100</span>
                {best.validation_status !== "validated" && <span className="text-[10px] text-warn">not validated</span>}
              </span>
            ) : (
              <span className={cn("text-xs", biasTone(i.overall?.label))}>{i.overall?.label ?? "—"} · no setup</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ overview
function Chip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border/60 bg-muted/40 px-2.5 py-0.5 text-xs">
      <span className="text-muted-foreground">{label}</span><span className={cn("font-medium", biasTone(value))}>{value}</span>
    </span>
  );
}

export function OverviewCard({ a }: { a: SignalAnalysis }) {
  const p = a.price_precision;
  const last = a.timeframes.find((t) => t.last_close !== undefined);
  const price = a.quote?.price ?? last?.last_close ?? null;
  const ov: Overall | null = a.overall;
  return (
    <Card data-testid="signal-overview">
      <CardContent className="grid gap-4 pt-5 md:grid-cols-[auto_1fr]">
        <div>
          <div className="text-xs text-muted-foreground">{a.name ?? a.symbol}</div>
          <div className="num text-2xl font-bold">{fmtPrice(price, p)}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            {a.quote && !a.quote.delayed ? `bid ${fmtPrice(a.quote.bid, p)} · ask ${fmtPrice(a.quote.ask, p)}` : "last stored close"}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <Badge variant={a.market_open === false ? "sell" : "buy"}>{a.market_open === false ? "market closed" : "market open"}</Badge>
            {a.session && <Badge variant="neutral">{a.session}</Badge>}
            <Badge variant="neutral" title={`provider status: ${a.provider_status}`}>{a.provider}</Badge>
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="text-xs text-muted-foreground">Overall bias</span>
            <span className={cn("text-lg font-semibold", biasTone(ov?.label))} data-testid="overall-bias">{ov?.label ?? "—"}</span>
            <span className="text-xs text-muted-foreground">{ov?.detail}</span>
          </div>
          {ov && <div className="flex flex-wrap gap-1.5">{Object.entries(ov.groups).map(([k, v]) => <Chip key={k} label={k} value={v} />)}</div>}
          <div className="text-xs text-muted-foreground">
            Spread model {a.spread_model !== null && a.spread_model !== undefined ? fmtPrice(a.spread_model, p) : "—"} round trip ·
            {" "}{a.counts ? `${a.counts.entry_ready} entry ready · ${a.counts.waiting} waiting · ${a.counts.developing} developing · ${a.counts.watchlist} watchlist` : ""}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ------------------------------------------------------------------------------------------------ best plan
function Levels({ plan, p }: { plan: TimeframePlan; p: number }) {
  return (
    <div className="num grid grid-cols-[auto_1fr_auto] gap-x-4 gap-y-1 text-sm" data-testid="plan-levels">
      <span className="text-muted-foreground">Entry ({plan.entry_type})</span>
      <span className="font-medium">{fmtPrice(plan.entry, p)}{plan.entry_zone ? <span className="ml-2 text-xs text-muted-foreground">zone {fmtPrice(plan.entry_zone[0], p)} – {fmtPrice(plan.entry_zone[1], p)}</span> : null}</span>
      <span />
      <span className="text-muted-foreground">Stop loss</span>
      <span className="font-medium text-bear">{fmtPrice(plan.stop_loss, p)}</span>
      <span className="text-xs text-muted-foreground">{fmtNum(plan.risk_atr, 2)} ATR</span>
      {plan.targets.map((t) => (
        <span key={t.label} className="contents">
          <span className="text-muted-foreground">{t.label}</span>
          <span className="font-medium text-bull">{fmtPrice(t.price, p)} <span className="text-xs font-normal text-muted-foreground">{words(t.basis)}</span></span>
          <span className="text-xs font-semibold">{fmtNum(t.rr, 2)}R</span>
        </span>
      ))}
      <span className="text-muted-foreground">Invalidation</span>
      <span>close {plan.side === "BUY" ? "below" : "above"} {fmtPrice(plan.invalidation, p)}</span>
      <span className="text-xs text-muted-foreground">cost {fmtNum(plan.cost_r, 2)}R</span>
    </div>
  );
}

function ProbabilityLine({ plan }: { plan: TimeframePlan }) {
  const tr = plan.track_record;
  return (
    <div className="space-y-0.5 text-xs text-muted-foreground" data-testid="probability">
      <p className="flex items-start gap-1"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />{plan.probability_note}</p>
      {tr?.available && tr.oos?.n_trades ? (
        <p>Backtest of these exact rules ({plan.timeframe}): {tr.oos.n_trades} out-of-sample trades, TP1 hit {fmtPct(tr.oos.tp1_hit_rate)}, expectancy {fmtNum(tr.oos.expectancy_r, 2)}R · verdict <strong>{words(tr.status)}</strong></p>
      ) : (
        <p>{tr?.summary ?? "No historical replay yet."}</p>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ timeframe table
export function TimeframeTable({ a, selected, onSelect }: { a: SignalAnalysis; selected: string | null; onSelect: (tf: string) => void }) {
  const rows = new Map<string, TimeframeRow>(a.timeframes.map((r) => [r.timeframe, r]));
  const p = a.price_precision;
  return (
    <Table data-testid="tf-table">
      <THead>
        <TR><TH>TF</TH><TH>Decision</TH><TH>Market</TH><TH>Technical state</TH><TH>Score</TH><TH className="text-right">Entry</TH><TH className="text-right">Stop</TH><TH className="text-right">TP1</TH><TH className="text-right">R:R</TH></TR>
      </THead>
      <TBody>
        {a.plans.map((pl) => {
          const r = rows.get(pl.timeframe);
          const lv = pl.call?.levels ?? pl.call?.hypothetical ?? null; // shown only for ENTER, or as hypothetical in experimental mode
          return (
            <TR key={pl.timeframe} data-testid={`tf-row-${pl.timeframe}`} onClick={() => onSelect(pl.timeframe)} aria-selected={selected === pl.timeframe}
              className={cn("cursor-pointer", selected === pl.timeframe && "bg-primary/5")}>
              <TD className="num font-semibold">{pl.timeframe}</TD>
              <TD><CallBadge call={pl.call} className="text-[10px]" /></TD>
              <TD>
                {r?.label ? (
                  <div><span className={cn("font-medium", biasTone(r.label))}>{r.label}</span>{r.structure && <span className="num ml-1 text-xs text-muted-foreground">{r.structure}</span>}</div>
                ) : <span className="text-xs text-muted-foreground">{pl.status === "insufficient_data" ? "not enough data" : r?.reason ?? "—"}</span>}
              </TD>
              <TD><StateBadge state={pl.state} /></TD>
              <TD className="num text-xs">
                {pl.buy_score === null && pl.sell_score === null ? "—" : (
                  <span><span className="text-bull">B {pl.buy_score ?? "—"}</span> / <span className="text-bear">S {pl.sell_score ?? "—"}</span></span>
                )}
              </TD>
              <TD className="num text-right">{lv ? fmtPrice(lv.entry, p) : "—"}</TD>
              <TD className="num text-right text-bear">{lv ? fmtPrice(lv.stop_loss, p) : "—"}</TD>
              <TD className="num text-right text-bull">{lv?.targets[0] ? fmtPrice(lv.targets[0].price, p) : "—"}</TD>
              <TD className="num text-right">{lv?.risk_reward ? `${fmtNum(lv.risk_reward, 2)}` : "—"}</TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}

// ------------------------------------------------------------------------------------------------ plan detail
export function Checklist({ plan }: { plan: Pick<TimeframePlan, "factors"> }) {
  return (
    <div className="space-y-3" data-testid="checklist">
      {plan.factors.map((f) => (
        <div key={f.key}>
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">{f.label}</span>
            <span className="num text-xs text-muted-foreground">{fmtNum(f.points, f.points % 1 ? 1 : 0)} / {f.max}</span>
          </div>
          <Meter value={f.max ? f.points / f.max : 0} className="my-1" />
          <ul className="space-y-0.5">
            {f.checks.map((c) => (
              <li key={c.key} className="flex items-start gap-2 text-xs">
                {c.max === 0 ? <CircleSlash className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-label="not applicable" />
                  : c.met ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-bull" aria-label="met" />
                    : <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-bear" aria-label="not met" />}
                <span><span className="font-medium">{c.label}</span> <span className="num text-muted-foreground">({fmtNum(c.points, c.points % 1 ? 1 : 0)}/{c.max})</span> — <span className="text-muted-foreground">{c.detail}</span></span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function PlanChart({ a, plan }: { a: SignalAnalysis; plan: TimeframePlan }) {
  const q = useSignalCandles(a.symbol, plan.timeframe, a.provider, plan.status !== "insufficient_data");
  const p = a.price_precision;
  const { lines, zones } = useMemo(() => {
    const ls: ChartLine[] = [];
    const zs: ChartZone[] = [];
    const lv = plan.call?.levels ?? plan.call?.hypothetical ?? null;
    if (lv && plan.side) {
      ls.push({ price: lv.entry, color: COLORS.primary, title: `${plan.call?.hypothetical ? "Hypothetical " : ""}Entry ${plan.side}` });
      ls.push({ price: lv.stop_loss, color: COLORS.bear, title: "SL", dashed: true });
      lv.targets.forEach((t) => ls.push({ price: t.price, color: COLORS.bull, title: t.label, dashed: true }));
    }
    if (plan.entry !== undefined && plan.side) {
      const first = q.data?.candles[Math.max(0, (q.data?.candles.length ?? 1) - 60)]?.time;
      if (plan.entry_zone && first) zs.push({ from: first, low: plan.entry_zone[0], high: plan.entry_zone[1], color: "rgba(59,91,219,0.12)", border: COLORS.primary, label: words(plan.zone_kind) });
    }
    return { lines: ls, zones: zs };
  }, [plan, q.data]);
  if (q.isLoading) return <Skeleton className="h-[360px] w-full" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data?.candles.length) return <EmptyState title="No stored candles for this timeframe" hint="Press Refresh to sync candles from the provider." />;
  return (
    <div data-testid="plan-chart">
      <CandleChart candles={q.data.candles} precision={p} lines={lines} zones={zones} height={360} resetKey={`${a.symbol}-${plan.timeframe}`} />
      <p className="mt-1 text-xs text-muted-foreground">{a.symbol} {plan.timeframe} · {a.provider} candles · blue = entry, red = stop, green = targets</p>
    </div>
  );
}

function SizeCalculator({ symbol, plan, p }: { symbol: string; plan: TimeframePlan; p: number }) {
  const { accountBalance, riskPct, contractSizes, set } = useSettings();
  const contract = contractSizes[symbol] ?? DEFAULT_CONTRACT_SIZE[symbol] ?? 1;
  const res = plan.entry !== undefined && plan.stop_loss !== undefined ? positionSize(accountBalance, riskPct, plan.entry, plan.stop_loss, contract) : null;
  return (
    <div className="space-y-2" data-testid="size-calculator">
      <div className="grid grid-cols-3 gap-2">
        <div><Label htmlFor="bal">Balance</Label><Input id="bal" type="number" min={0} value={accountBalance} onChange={(e) => set({ accountBalance: Number(e.target.value) })} /></div>
        <div><Label htmlFor="risk">Risk %</Label><Input id="risk" type="number" min={0} step={0.1} value={riskPct} onChange={(e) => set({ riskPct: Number(e.target.value) })} /></div>
        <div><Label htmlFor="cs">Contract size</Label><Input id="cs" type="number" min={0} value={contract} onChange={(e) => set({ contractSizes: { ...contractSizes, [symbol]: Number(e.target.value) } })} /></div>
      </div>
      {res ? (
        <p className="num text-sm" data-testid="size-result">
          Risk <strong>{fmtNum(res.riskAmount, 2)}</strong> over a {fmtPrice(res.stopDistance, p)} stop → <strong>{fmtNum(res.lots, 3)} lots</strong>
          <span className="text-muted-foreground"> ({fmtNum(res.units, 4)} units)</span>
        </p>
      ) : <p className="text-xs text-muted-foreground">Enter a positive balance, risk and contract size.</p>}
      <p className="text-[11px] text-muted-foreground">Check your broker&apos;s contract specification (lot size, minimum lot, margin). Account currency is assumed to be USD.</p>
    </div>
  );
}

export function PlanDetail({ a, tf }: { a: SignalAnalysis; tf: string }) {
  const plan = a.plans.find((x) => x.timeframe === tf);
  if (!plan) return null;
  const p = a.price_precision;
  const hasPlan = !!plan.side && plan.targets.length > 0;
  const showLevels = hasPlan && !!(plan.call?.levels ?? plan.call?.hypothetical);
  return (
    <Card data-testid="plan-detail">
      <CardHeader>
        <CardTitle>{a.symbol} {plan.timeframe} — {plan.group_label}</CardTitle>
        <span className="text-xs text-muted-foreground">bias {plan.bias_tfs.join(" + ") || "none"} · confirmation {plan.confirm_tf}</span>
      </CardHeader>
      <CardContent className="space-y-5">
        {plan.call && <CallCard call={plan.call} symbol={a.symbol} precision={p} title={`Decision · ${plan.timeframe}`} />}
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground" data-testid="technical-state">
          <span className="text-[11px] font-semibold uppercase tracking-wider">Technical analysis</span>
          <StateBadge state={plan.state} />
          {plan.side && <span>{plan.side} {words(plan.setup_type)} · {plan.score}/100{plan.checks_total ? ` · ${plan.checks_met}/${plan.checks_total} checks met` : ""}</span>}
        </div>
        {plan.previous && (
          <p className="rounded-md border border-warn/30 bg-warn/5 p-2 text-xs text-warn">Previous {plan.previous.side} plan (entry {fmtPrice(plan.previous.entry, p)}): {plan.previous.reason}.</p>
        )}
        {plan.market && (
          <p className="text-sm"><span className={cn("font-medium", biasTone(plan.market.label))}>{plan.market.label}</span>
            {plan.market.structure && <span className="num text-muted-foreground"> ({plan.market.structure})</span>} — {plan.market.observation}</p>
        )}
        {!hasPlan ? (
          <div className="space-y-1 text-sm">
            {plan.reasons_against.map((r, i) => <p key={i} className="text-muted-foreground">• {r}</p>)}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div className="space-y-4">
                {showLevels ? <Levels plan={plan} p={p} /> : (
                  <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground" data-testid="levels-hidden">
                    Entry, stop and targets are shown only with an ENTER decision, or marked hypothetical in experimental analysis mode.
                  </p>
                )}
                {showLevels && plan.conditions.length > 0 && (
                  <div><div className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Conditions</div>
                    <ul className="space-y-1 text-sm">{plan.conditions.map((c, i) => <li key={i}>• {c}</li>)}</ul></div>
                )}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div><div className="mb-1 text-xs font-semibold uppercase tracking-wider text-bull">Reasons for</div>
                    <ul className="space-y-1 text-xs" data-testid="reasons-for">{plan.reasons_for.map((r, i) => <li key={i}>• {r}</li>)}</ul></div>
                  <div><div className="mb-1 text-xs font-semibold uppercase tracking-wider text-bear">Reasons against</div>
                    <ul className="space-y-1 text-xs" data-testid="reasons-against">{plan.reasons_against.map((r, i) => <li key={i}>• {r}</li>)}</ul></div>
                </div>
                {showLevels && plan.reasoning && (
                  <div className="space-y-1 text-xs text-muted-foreground">
                    <p><strong className="text-foreground">Entry:</strong> {plan.reasoning.entry}</p>
                    <p><strong className="text-foreground">Stop:</strong> {plan.reasoning.stop}</p>
                    <p><strong className="text-foreground">Targets:</strong> {plan.reasoning.targets.join(" · ")}</p>
                  </div>
                )}
                <ProbabilityLine plan={plan} />
              </div>
              <div className="space-y-4">
                <div><div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Confluence checklist ({plan.score}/100)</div><Checklist plan={plan} /></div>
                {showLevels && <div><div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Position size{plan.call?.hypothetical ? " (hypothetical)" : ""}</div><SizeCalculator symbol={a.symbol} plan={plan} p={p} /></div>}
              </div>
            </div>
            <PlanChart a={a} plan={plan} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

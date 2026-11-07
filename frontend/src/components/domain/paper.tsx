"use client";

import { AlertTriangle } from "lucide-react";
import { Fragment, useState } from "react";
import { EmptyState, QueryState } from "@/components/domain/common";
import { Checklist, SideBadge } from "@/components/domain/signals";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Stat } from "@/components/ui/card";
import { FieldError, Input, Label } from "@/components/ui/form";
import { Tabs } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { usePaperTrade, useResetPaperAccount, useUpdatePaperAccount } from "@/lib/hooks";
import type { BreakdownKey, BreakdownRow, PaperAccountSummary, PaperSummary, PaperTrade, PaperWorker } from "@/lib/paper-types";
import { cn, fmtDate, fmtNum, fmtPct, fmtPrice, signClass, timeAgo } from "@/lib/utils";

// ---- formatting ----
export const fmtR = (v: number | null | undefined) => (v === null || v === undefined || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}R`);
export function fmtMoney(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = `$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return v < 0 ? `−${s}` : signed && v > 0 ? `+${s}` : s;
}
const px = (v: number | null | undefined) => fmtPrice(v, v !== null && v !== undefined && Math.abs(v) < 10 ? 4 : 2);
const words = (s?: string | null) => (s ?? "").replace(/_/g, " ");

// ---- status ----
type Variant = "neutral" | "buy" | "sell" | "wait" | "info";
const UNFILLED: Record<string, string> = { cancelled: "Cancelled", missed: "Missed", expired: "Expired", skipped: "Skipped" };

export function PaperStatusBadge({ t }: { t: Pick<PaperTrade, "status" | "exit_reason" | "order_type"> }) {
  let label: string;
  let variant: Variant = "neutral";
  if (t.status === "closed") {
    label = t.exit_reason === "target" ? "TP1 hit" : "Stopped out";
    variant = t.exit_reason === "target" ? "buy" : "sell";
  } else if (t.status === "open") {
    label = "Open";
    variant = "info";
  } else if (t.status === "pending") {
    label = t.order_type === "limit" ? "Limit resting" : "Awaiting fill";
    variant = "wait";
  } else {
    label = UNFILLED[t.status] ?? t.status;
  }
  return <Badge variant={variant} data-testid="paper-status">{label}</Badge>;
}

export function WorkerLine({ w }: { w: PaperWorker }) {
  if (!w.enabled) {
    return (
      <p role="note" className="flex items-start gap-2 rounded-md border border-warn/30 bg-warn/5 p-3 text-sm text-warn">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <span>Automatic paper trading is off (PAPER_TRADING_INTERVAL_SECONDS=0). Signals are only recorded when you press “Run cycle now”.</span>
      </p>
    );
  }
  return (
    <p className="text-xs text-muted-foreground" data-testid="worker-line">
      Automatic cycle every {w.interval_s}s (sync → analyse → record → simulate) ·{" "}
      {w.running ? "running now" : `last cycle ${timeAgo(w.last_cycle_at)}${w.last_duration_s !== null ? ` (${fmtNum(w.last_duration_s, 1)}s)` : ""}`} ·{" "}
      {w.cycles} cycle{w.cycles === 1 ? "" : "s"} since the backend started
      {w.last_error && <span className="text-bear"> · last error: {w.last_error}</span>}
    </p>
  );
}

// ---- verdict & statistics ----
const VERDICT_TITLE: Record<string, string> = {
  collecting: "Collecting evidence",
  no_edge: "No edge detected",
  negative: "Losing so far",
  validated: "Positive so far (passes the same bar as the backtest)",
};

export function VerdictCard({ s }: { s: PaperSummary }) {
  const v = s.forward.verdict;
  const pct = Math.min(1, v.n / v.needed);
  return (
    <Card>
      <CardContent className="space-y-3 pt-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className={cn("text-lg font-semibold", v.status === "negative" && "text-bear", v.status === "validated" && "text-bull")}>{VERDICT_TITLE[v.status]}</h2>
          <span className="num text-sm text-muted-foreground">{v.n} / {v.needed} closed trades</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded bg-muted" role="progressbar" aria-label="Closed trades toward a verdict" aria-valuemin={0} aria-valuemax={v.needed} aria-valuenow={v.n}>
          <div className="h-full rounded bg-primary" style={{ width: `${pct * 100}%` }} />
        </div>
        <p className="text-sm text-muted-foreground">{v.summary}.</p>
        <p className="text-xs text-muted-foreground">
          Backtest of the same rules, out-of-sample part: <span className={cn("num font-medium", signClass(s.backtest.expectancy_r))}>{fmtR(s.backtest.expectancy_r)}</span> per trade over{" "}
          {s.backtest.n_trades} trades. The live record decides; a short streak in either direction is noise.
        </p>
      </CardContent>
    </Card>
  );
}

export function ForwardStats({ s }: { s: PaperSummary }) {
  const f = s.forward;
  const c = f.counts;
  const ci = f.expectancy_r_ci_low !== undefined && f.expectancy_r_ci_low !== null ? `95% CI ${fmtR(f.expectancy_r_ci_low)} … ${fmtR(f.expectancy_r_ci_high)}` : "needs 2+ trades";
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4" data-testid="forward-stats">
      <Stat label="Signals recorded" value={f.signals_recorded} sub={f.since ? `since ${fmtDate(f.since, false)}` : "none yet"} />
      <Stat label="Closed trades" value={f.n_trades} sub={`${c.open} open · ${c.pending} pending`} />
      <Stat label="Win rate" value={fmtPct(f.win_rate)} sub="TP1 before the stop" />
      <Stat label="Expectancy" value={<span className={signClass(f.expectancy_r)}>{fmtR(f.expectancy_r)}</span>} sub={ci} />
      <Stat label="Total" value={<span className={signClass(f.total_r)}>{fmtR(f.total_r)}</span>} sub="net of spread" />
      <Stat label="Profit factor" value={fmtNum(f.profit_factor)} />
      <Stat label="Max drawdown" value={f.max_drawdown_r !== undefined ? `${fmtNum(f.max_drawdown_r)}R` : "—"} />
      <Stat label="Limit fill rate" value={fmtPct(f.limit_fill_rate)} sub={`${c.cancelled + c.missed + c.expired + c.skipped} never filled`} />
    </div>
  );
}

// ---- equity curve (single series: the card title names it, so no legend) ----
export function EquityCurve({ points, label }: { points: { t: string; v: number }[]; label: string }) {
  const [hover, setHover] = useState<number | null>(null);
  if (points.length < 2) {
    return <EmptyState title="The curve starts after the second closed trade" hint="Each closed paper trade adds its R (net of the spread) in the order it closed." />;
  }
  const W = 640;
  const H = 200;
  const P = { l: 40, r: 12, t: 12, b: 12 };
  const vals = [0, ...points.map((p) => p.v)];
  const n = vals.length - 1;
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const x = (i: number) => P.l + (i / n) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - (v - lo) / span) * (H - P.t - P.b);
  const d = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = vals[n];
  const pick = (clientX: number, rect: DOMRect) => setHover(Math.max(1, Math.min(n, Math.round(((clientX - rect.left) / rect.width * W - P.l) / (W - P.l - P.r) * n))));
  const h = hover !== null ? points[hover - 1] : null;
  return (
    <figure className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full touch-none outline-none focus-visible:ring-2 focus-visible:ring-primary"
        role="img"
        aria-label={`${label}: ${n} closed trades, now ${fmtR(last)}`}
        tabIndex={0}
        onPointerMove={(e) => pick(e.clientX, e.currentTarget.getBoundingClientRect())}
        onPointerLeave={() => setHover(null)}
        onBlur={() => setHover(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") setHover((v) => Math.min(n, (v ?? 0) + 1));
          if (e.key === "ArrowLeft") setHover((v) => Math.max(1, (v ?? n + 1) - 1));
        }}
      >
        <line x1={P.l} x2={W - P.r} y1={y(0)} y2={y(0)} className="stroke-border" strokeWidth={1} />
        <text x={P.l - 6} y={y(0) + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">0R</text>
        {hi > 0 && <text x={P.l - 6} y={P.t + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{fmtR(hi)}</text>}
        {lo < 0 && <text x={P.l - 6} y={H - P.b} textAnchor="end" className="fill-muted-foreground text-[11px]">{fmtR(lo)}</text>}
        <path d={d} fill="none" className="stroke-primary" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={P.t} y2={H - P.b} className="stroke-muted-foreground" strokeWidth={1} />}
        <circle cx={x(hover ?? n)} cy={y(vals[hover ?? n])} r={4} className="fill-primary stroke-card" strokeWidth={2} />
      </svg>
      {h && hover !== null && (
        <div
          role="status"
          className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-md border bg-card px-2 py-1 text-xs shadow-soft"
          style={{ left: `${Math.min(85, Math.max(15, (x(hover) / W) * 100))}%` }}
        >
          <div className="font-medium">Trade {hover} · {fmtDate(h.t)}</div>
          <div className="num">{label}: {fmtR(h.v)} (this trade {fmtR(h.v - vals[hover - 1])})</div>
        </div>
      )}
      <figcaption className="mt-1 flex justify-between text-xs text-muted-foreground">
        <span>trade 1</span>
        <span>now <span className={cn("num font-medium", signClass(last))}>{fmtR(last)}</span></span>
        <span>trade {n}</span>
      </figcaption>
    </figure>
  );
}

// ---- account ----
function AccountSettings({ a }: { a: PaperAccountSummary }) {
  const update = useUpdatePaperAccount();
  const reset = useResetPaperAccount();
  const [risk, setRisk] = useState(String(a.risk_pct));
  const [maxOpen, setMaxOpen] = useState(String(a.max_open_positions));
  const [dailyLoss, setDailyLoss] = useState(String(a.max_daily_loss_pct));
  const [balance, setBalance] = useState(String(a.start_balance));
  const r = Number(risk);
  const m = Number(maxOpen);
  const dl = Number(dailyLoss);
  const b = Number(balance);
  const errors = {
    risk: r > 0 && r <= 5 ? undefined : "0.01–5%",
    maxOpen: Number.isInteger(m) && m >= 1 && m <= 50 ? undefined : "1–50",
    dailyLoss: dl > 0 && dl <= 50 ? undefined : "0.1–50%",
    balance: b > 0 ? undefined : "must be above 0",
  };
  const rulesOk = !errors.risk && !errors.maxOpen && !errors.dailyLoss;
  const onReset = () => {
    if (!rulesOk || errors.balance) return;
    if (typeof window !== "undefined" && !window.confirm(`Start a new paper account with ${fmtMoney(b)}? Recorded signals and the forward-test record are kept.`)) return;
    reset.mutate({ start_balance: b, risk_pct: r, max_open_positions: m, max_daily_loss_pct: dl });
  };
  return (
    <form
      className="space-y-3"
      aria-label="Paper account rules"
      onSubmit={(e) => {
        e.preventDefault();
        if (rulesOk) update.mutate({ risk_pct: r, max_open_positions: m, max_daily_loss_pct: dl });
      }}
    >
      <div className="grid grid-cols-3 gap-3">
        <div>
          <Label htmlFor="paper-risk">Risk per trade %</Label>
          <Input id="paper-risk" inputMode="decimal" value={risk} onChange={(e) => setRisk(e.target.value)} />
          <FieldError message={errors.risk} />
        </div>
        <div>
          <Label htmlFor="paper-max-open">Max open trades</Label>
          <Input id="paper-max-open" inputMode="numeric" value={maxOpen} onChange={(e) => setMaxOpen(e.target.value)} />
          <FieldError message={errors.maxOpen} />
        </div>
        <div>
          <Label htmlFor="paper-daily-loss">Daily loss limit %</Label>
          <Input id="paper-daily-loss" inputMode="decimal" value={dailyLoss} onChange={(e) => setDailyLoss(e.target.value)} />
          <FieldError message={errors.dailyLoss} />
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Button type="submit" size="sm" loading={update.isPending} disabled={!rulesOk}>Save rules</Button>
        <div className="ml-auto flex items-end gap-2">
          <div>
            <Label htmlFor="paper-balance">New account balance $</Label>
            <Input id="paper-balance" inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} className="w-32" />
          </div>
          <Button type="button" size="sm" variant="outline" onClick={onReset} loading={reset.isPending} disabled={!rulesOk || !!errors.balance}>Reset account</Button>
        </div>
      </div>
      {(update.isError || reset.isError) && <p className="text-xs text-bear">{String((update.error ?? reset.error)?.message ?? "Request failed")}</p>}
      {update.isSuccess && <p className="text-xs text-muted-foreground">Saved: the rules apply to signals recorded from now on.</p>}
    </form>
  );
}

export function AccountCard({ a }: { a: PaperAccountSummary }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{a.name}</CardTitle>
        <span className="text-xs text-muted-foreground">opened {fmtDate(a.created_at, false)} with {fmtMoney(a.start_balance)}</span>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3" data-testid="account-stats">
          <Stat label="Balance" value={fmtMoney(a.balance)} sub={a.return_pct !== null ? `${a.return_pct > 0 ? "+" : ""}${fmtNum(a.return_pct)}% since start` : undefined} />
          <Stat label="Equity" value={fmtMoney(a.equity)} sub={`open P&L ${fmtMoney(a.unrealized_pnl, true)}`} />
          <Stat label="Today" value={<span className={signClass(a.today_pnl)}>{fmtMoney(a.today_pnl, true)}</span>} sub="realised, UTC day" />
          <Stat label="Risk per trade" value={fmtMoney(a.risk_per_trade)} sub={`${fmtNum(a.risk_pct)}% of balance`} />
          <Stat label="Max drawdown" value={fmtMoney(a.max_drawdown)} sub="closed trades" />
          <Stat label="Trades taken" value={a.metrics.n_trades} sub={`${a.skipped_signals} signal${a.skipped_signals === 1 ? "" : "s"} skipped by the rules`} />
        </div>
        <p className={cn("text-sm", a.can_trade ? "text-muted-foreground" : "text-warn")} data-testid="account-gate">
          {a.can_trade ? `Taking new signals: ${a.live_trades} of ${a.max_open_positions} trade slots in use.` : `Not taking new signals: ${a.blocked_reason}.`}
        </p>
        <AccountSettings key={`${a.id}-${a.risk_pct}-${a.max_open_positions}-${a.max_daily_loss_pct}`} a={a} />
      </CardContent>
    </Card>
  );
}

// ---- trades ----
function TradeDetail({ id }: { id: number }) {
  const q = usePaperTrade(id);
  return (
    <QueryState query={q}>
      {(t) => (
        <div className="grid gap-4 p-3 lg:grid-cols-2" data-testid="paper-trade-detail">
          <div className="space-y-2 text-sm">
            <p className="font-medium">{t.summary ?? `${t.direction} ${t.timeframe}`}</p>
            <ul className="space-y-0.5 text-xs text-muted-foreground">
              <li>Signal candle closed {fmtDate(t.signal_time)} · seen by the backend {fmtDate(t.detected_at)}</li>
              <li>{t.order_type === "limit" ? `Limit ${px(t.entry_price)}` : `Market order (planned entry ${px(t.entry_price)})`} · stop {px(t.stop_loss)} · TP1 {px(t.take_profit)} · valid until {fmtDate(t.valid_until)}</li>
              {t.filled_at && <li>Filled {px(t.fill_price)} at {fmtDate(t.filled_at)} · risk {px(t.risk)} · spread cost {fmtNum(t.spread_r)}R</li>}
              {t.closed_at && <li>{t.status === "closed" ? `Closed ${px(t.exit_price)}` : UNFILLED[t.status] ?? t.status} at {fmtDate(t.closed_at)}{t.note ? `: ${t.note}` : ""}</li>}
              {t.mfe_r !== null && <li>Best {fmtR(t.mfe_r)} · worst {fmtR(t.mae_r)} while open (before costs)</li>}
              <li>{t.account_taken ? `Taken by the account, risking ${fmtMoney(t.risk_amount)}` : `Not taken by the account: ${t.account_note ?? "account rules"}`}</li>
            </ul>
            {!!t.plan?.reasons_for?.length && (
              <div>
                <div className="text-xs font-medium">Reasons for</div>
                <ul className="list-disc pl-4 text-xs text-muted-foreground">{t.plan.reasons_for.slice(0, 6).map((x) => <li key={x}>{x}</li>)}</ul>
              </div>
            )}
            {!!t.plan?.reasons_against?.length && (
              <div>
                <div className="text-xs font-medium">Reasons against</div>
                <ul className="list-disc pl-4 text-xs text-muted-foreground">{t.plan.reasons_against.slice(0, 6).map((x) => <li key={x}>{x}</li>)}</ul>
              </div>
            )}
          </div>
          {t.plan?.factors?.length ? <Checklist plan={{ factors: t.plan.factors }} /> : <p className="text-xs text-muted-foreground">No checklist stored for this signal.</p>}
        </div>
      )}
    </QueryState>
  );
}

type TableKind = "open" | "pending" | "history";
const HEADERS: Record<TableKind, string[]> = {
  open: ["Instrument", "Side", "Fill", "Stop", "TP1", "Last", "Open P&L", "Opened", "Score", "Account"],
  pending: ["Instrument", "Side", "Order", "Stop", "TP1", "Expires", "Score", "Account"],
  history: ["Closed", "Instrument", "Side", "Result", "Entry → exit", "R net", "P&L", "Score", "Setup"],
};

function Cells({ t, kind }: { t: PaperTrade; kind: TableKind }) {
  const inst = <TD className="whitespace-nowrap font-medium">{t.symbol} <span className="text-muted-foreground">{t.timeframe}</span></TD>;
  const side = <TD><SideBadge side={t.direction} /></TD>;
  const score = <TD className="num">{t.score ?? "—"}</TD>;
  const account = <TD className="text-xs">{t.account_taken ? fmtMoney(t.risk_amount) : <span className="text-muted-foreground" title={t.account_note ?? undefined}>skipped</span>}</TD>;
  if (kind === "open") {
    return (<>{inst}{side}<TD className="num">{px(t.fill_price)}</TD><TD className="num">{px(t.stop_loss)}</TD><TD className="num">{px(t.take_profit)}</TD>
      <TD className="num">{px(t.last_price)}</TD>
      <TD className={cn("num whitespace-nowrap", signClass(t.unrealized_r))}>{fmtR(t.unrealized_r)}{t.unrealized_pnl !== null && <span className="text-xs"> {fmtMoney(t.unrealized_pnl, true)}</span>}</TD>
      <TD className="whitespace-nowrap text-xs">{timeAgo(t.filled_at)}</TD>{score}{account}</>);
  }
  if (kind === "pending") {
    return (<>{inst}{side}<TD className="whitespace-nowrap">{t.order_type === "limit" ? `Limit ${px(t.entry_price)}` : "Market · next open"}</TD>
      <TD className="num">{px(t.stop_loss)}</TD><TD className="num">{px(t.take_profit)}</TD><TD className="whitespace-nowrap text-xs">{fmtDate(t.valid_until)}</TD>{score}{account}</>);
  }
  return (<><TD className="whitespace-nowrap text-xs">{fmtDate(t.closed_at)}</TD>{inst}{side}<TD><PaperStatusBadge t={t} /></TD>
    <TD className="num whitespace-nowrap">{t.fill_price !== null ? `${px(t.fill_price)} → ${px(t.exit_price)}` : <span className="text-muted-foreground">not filled</span>}</TD>
    <TD className={cn("num", signClass(t.r_net))}>{fmtR(t.r_net)}</TD>
    <TD className={cn("num whitespace-nowrap", signClass(t.pnl))}>{t.account_taken && t.status === "closed" ? fmtMoney(t.pnl, true) : "—"}</TD>
    {score}<TD className="text-xs">{words(t.setup_type)}</TD></>);
}

export function TradesTable({ trades, kind }: { trades: PaperTrade[]; kind: TableKind }) {
  const [open, setOpen] = useState<number | null>(null);
  const cols = HEADERS[kind].length;
  return (
    <div className="overflow-x-auto">
      <Table>
        <THead><TR>{HEADERS[kind].map((h) => <TH key={h}>{h}</TH>)}</TR></THead>
        <TBody>
          {trades.map((t) => (
            <Fragment key={t.id}>
              <TR
                className="cursor-pointer"
                tabIndex={0}
                aria-expanded={open === t.id}
                onClick={() => setOpen(open === t.id ? null : t.id)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(open === t.id ? null : t.id); } }}
              >
                <Cells t={t} kind={kind} />
              </TR>
              {open === t.id && <tr><td colSpan={cols} className="bg-muted/30"><TradeDetail id={t.id} /></td></tr>}
            </Fragment>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

// ---- breakdowns ----
const BREAKDOWN_TABS: { id: BreakdownKey; label: string }[] = [
  { id: "series", label: "Instrument × TF" },
  { id: "timeframe", label: "Timeframe" },
  { id: "symbol", label: "Instrument" },
  { id: "setup_type", label: "Setup" },
  { id: "score_band", label: "Score" },
  { id: "direction", label: "Side" },
  { id: "order_type", label: "Order" },
  { id: "session", label: "Session" },
];

export function Breakdowns({ s }: { s: PaperSummary }) {
  const [key, setKey] = useState<BreakdownKey>("series");
  const rows: BreakdownRow[] = s.breakdowns[key] ?? [];
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto"><Tabs tabs={BREAKDOWN_TABS} value={key} onChange={setKey} /></div>
      {rows.length === 0 ? (
        <EmptyState title="No closed trades yet" hint="Results per instrument, timeframe, setup and score band appear as paper trades close." />
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <THead><TR><TH>Group</TH><TH>Trades</TH><TH>Win rate</TH><TH>Expectancy</TH><TH>Total</TH>{key === "series" && <TH>Backtest (out-of-sample)</TH>}</TR></THead>
            <TBody>
              {rows.map((g) => (
                <TR key={g.key}>
                  <TD className="font-medium">{g.key}</TD>
                  <TD className="num">{g.n}</TD>
                  <TD className="num">{fmtPct(g.win_rate)}</TD>
                  <TD className={cn("num", signClass(g.expectancy_r))}>{fmtR(g.expectancy_r)}</TD>
                  <TD className={cn("num", signClass(g.total_r))}>{fmtR(g.total_r)}</TD>
                  {key === "series" && (
                    <TD className="num text-xs">{g.backtest ? `${fmtR(g.backtest.expectancy_r)} over ${g.backtest.n_trades ?? 0} (${words(g.backtest.status)})` : "not backtested"}</TD>
                  )}
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}
      <p className="text-xs text-muted-foreground">Small groups are noise: a group needs about 100 closed trades before its expectancy means anything.</p>
    </div>
  );
}

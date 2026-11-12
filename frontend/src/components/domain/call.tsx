"use client";

// Displays the backend's trading decision (app/decision). Nothing here decides: every word and level comes from the `call` object.

import { AlertTriangle, ArrowRight, CheckCircle2, CircleSlash, FlaskConical, XCircle } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { CallDecision, CallLevels, TradeCall, TradeManagement } from "@/lib/decision-types";
import { cn, fmtNum, fmtPrice, fmtSignedR } from "@/lib/utils";

const TONE: Record<CallDecision, { box: string; text: string; badge: "buy" | "wait" | "sell" | "neutral" | "info" }> = {
  ENTER: { box: "border-bull/40 bg-bull/10", text: "text-bull", badge: "buy" },
  HOLD: { box: "border-primary/40 bg-primary/5", text: "text-primary", badge: "info" },
  WAIT: { box: "border-warn/40 bg-cta/10", text: "text-warn", badge: "wait" },
  EXIT: { box: "border-bear/40 bg-bear/10", text: "text-bear", badge: "sell" },
  "NO TRADE": { box: "border-border bg-muted/60", text: "text-muted-foreground", badge: "neutral" },
};

export const callVariant = (d?: CallDecision | null) => (d ? TONE[d].badge : "neutral");

/** One matrix cell: the decision word, the reason after the dash in small type, the full sentence on hover. */
export function ShortCall({ label, decision, headline, className }: { label?: string | null; decision?: CallDecision | null; headline?: string | null; className?: string }) {
  if (!label || !decision) return <span className="text-xs text-muted-foreground">—</span>;
  const [word, why] = label.split(" — ");
  return (
    <Badge variant={callVariant(decision)} className={cn("flex-col items-start gap-0 whitespace-nowrap rounded-md px-1.5 py-0.5 leading-tight", className)}
      title={headline ? `${label}: ${headline}` : label}>
      <span className="text-[10px] font-semibold">{word}</span>
      {why && <span className="text-[9px] font-medium lowercase opacity-90">{why}</span>}
    </Badge>
  );
}

/** Compact call for tables and tabs: the full label (e.g. "WAIT — UNVALIDATED SETUP"). */
export function CallBadge({ call, className }: { call?: TradeCall | null; className?: string }) {
  if (!call) return <Badge variant="neutral" className={className}>—</Badge>;
  return (
    <Badge variant={TONE[call.decision].badge} className={cn("whitespace-nowrap font-semibold", className)} title={call.headline} data-testid="call-badge">
      {call.label}
    </Badge>
  );
}

function Field({ label, children, testId }: { label: string; children: React.ReactNode; testId?: string }) {
  return (
    <div data-testid={testId}>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-sm">{children}</div>
    </div>
  );
}

function LevelsGrid({ lv, p }: { lv: CallLevels; p: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Field label={lv.entry_zone ? "Entry (zone)" : "Entry"}>
        <span className="num font-semibold">{fmtPrice(lv.entry, p)}</span>
        {lv.entry_zone && <span className="num block text-xs text-muted-foreground">{fmtPrice(lv.entry_zone[0], p)} – {fmtPrice(lv.entry_zone[1], p)}</span>}
      </Field>
      <Field label="Stop-loss"><span className="num font-semibold text-bear">{fmtPrice(lv.stop_loss, p)}</span></Field>
      <Field label="Take-profit">
        {lv.targets.length ? lv.targets.map((t) => (
          <span key={t.label} className="num block text-bull">{t.label} {fmtPrice(t.price, p)}{t.rr != null ? ` (${fmtNum(t.rr, 2)}R)` : ""}</span>
        )) : "—"}
      </Field>
      <Field label="Reward:risk"><span className="num font-semibold">{lv.risk_reward != null ? `1:${fmtNum(lv.risk_reward, 2)}` : "—"}</span></Field>
    </div>
  );
}

const signedR = (r: number) => fmtSignedR(r, 1);

/** One line for tables: the held paper trade's side, entry, stop, first target and open result in R. */
export function TradeBrief({ m, p, className }: { m: TradeManagement; p: number; className?: string }) {
  return (
    <span className={cn("num block text-[11px] text-muted-foreground", className)} data-testid="trade-brief">
      {m.status === "pending" ? "limit " : ""}{m.direction} {m.status === "pending" ? "at" : "from"} {fmtPrice(m.entry_price, p)} · SL {fmtPrice(m.stop_loss, p)} · TP1{" "}
      {fmtPrice(m.take_profit, p)}
      {m.unrealized_r != null && <> · <span className={m.unrealized_r >= 0 ? "text-bull" : "text-bear"}>{signedR(m.unrealized_r)} open</span></>}
    </span>
  );
}

/** One line for tables (experimental mode only): an unvalidated setup's hypothetical entry, stop, first target and reward:risk. */
export function HypoBrief({ lv, p, className }: { lv: NonNullable<TradeCall["hypothetical"]>; p: number; className?: string }) {
  const tp1 = lv.targets?.[0];
  return (
    <span className={cn("num block text-[11px] text-warn", className)} data-testid="hypo-brief" title={lv.note}>
      Hypothetical {lv.direction}: entry {fmtPrice(lv.entry, p)} · SL {fmtPrice(lv.stop_loss, p)}
      {tp1 ? ` · TP1 ${fmtPrice(tp1.price, p)}` : ""}{lv.risk_reward != null ? ` · 1:${fmtNum(lv.risk_reward, 2)}` : ""}
    </span>
  );
}

export function TradeManagementLine({ m, p }: { m: TradeManagement; p: number }) {
  const tone = m.action === "EXIT" ? "text-bear" : m.action === "HOLD" ? "text-bull" : "text-warn";
  return (
    <div className="rounded-md border p-3 text-sm" data-testid="trade-management">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Tracked paper trade #{m.trade_id}</span>
        <span className={cn("font-semibold", tone)}>{m.action}</span>
        <span className="text-xs text-muted-foreground">{m.direction} · {m.status}</span>
      </div>
      <p className="mt-1">{m.reason}</p>
      <p className="num mt-1 text-xs text-muted-foreground">
        entry {fmtPrice(m.entry_price, p)} · now {fmtPrice(m.current_price, p)} · stop {fmtPrice(m.stop_loss, p)} ({fmtPrice(m.stop_distance, p)} away)
        · target {fmtPrice(m.take_profit, p)} ({fmtPrice(m.target_distance, p)} away)
        {m.unrealized_r != null ? ` · unrealized ${fmtNum(m.unrealized_r, 2)}R` : ""}{m.unrealized_pnl != null ? ` ($${fmtNum(m.unrealized_pnl, 2)})` : ""}
      </p>
    </div>
  );
}

/** The decision panel: readable in three seconds (decision, direction, what comes next), with the detail below. */
export function CallCard({ call, symbol, precision = 2, title, compact = false }: { call: TradeCall; symbol: string; precision?: number; title?: string; compact?: boolean }) {
  const t = TONE[call.decision];
  const p = precision;
  const unvalidated = call.validation.status !== "validated";
  const against = [...(call.failed_checks ?? []).map((c) => `${c.name}: ${c.detail}`), ...(call.reasons_against ?? [])].slice(0, 5);
  return (
    <section className={cn("rounded-2xl border-2 p-4 sm:p-5", t.box)} data-testid="call-card" aria-label={`${title ?? "Decision"} for ${symbol}${call.timeframe ? ` ${call.timeframe}` : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">{title ?? "Decision"}</div>
          <div className={cn("text-2xl font-bold tracking-tight sm:text-3xl", t.text)} data-testid="call-decision">{call.label}</div>
          <div className="mt-1 text-sm font-medium">
            {symbol} · {call.direction === "NONE" ? "no direction" : call.direction} · {call.timeframe ?? "all timeframes"}
            {call.setup ? ` · ${call.setup}` : ""}{call.entry_mode ? ` · ${call.entry_mode} entry` : ""}
          </div>
        </div>
        <Badge variant={unvalidated ? "wait" : "buy"} className="shrink-0" title={call.validation.note} data-testid="call-validation">
          Research: {call.validation.label}
        </Badge>
      </div>
      <p className="mt-3 text-sm" data-testid="call-headline">{call.headline}</p>
      {call.next_condition && (
        <p className="mt-2 flex items-start gap-1.5 text-sm" data-testid="call-next">
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span><strong>Next:</strong> {call.next_condition}</span>
        </p>
      )}
      {call.invalidation && <p className="mt-1 text-xs text-muted-foreground">Invalidated by: {call.invalidation}</p>}

      <div className="mt-4 space-y-4 rounded-xl bg-surface/80 p-3 sm:p-4">
        {call.levels ? (
          <LevelsGrid lv={call.levels} p={p} />
        ) : call.watch?.zone ? (
          <Field label="Price condition">
            <span className="num">zone {fmtPrice(call.watch.zone[0], p)} – {fmtPrice(call.watch.zone[1], p)}</span>
            {call.watch.invalidation != null && <span className="num text-muted-foreground"> · invalid beyond {fmtPrice(call.watch.invalidation, p)}</span>}
            <span className="block text-xs text-muted-foreground">Entry, stop and targets are shown only with an ENTER decision.</span>
          </Field>
        ) : null}
        <div className={cn("grid grid-cols-1 gap-3", !compact && "sm:grid-cols-3")}>
          {!call.trade && <Field label="Confirmation">{call.alignment?.confirmation ? `${call.alignment.confirmation.timeframe}: ${call.alignment.confirmation.status}` : call.technical_status ?? "—"}</Field>}
          <Field label="Data quality" testId="call-data">
            <span className={call.data_quality.status === "ok" ? "" : "text-bear"}>{call.data_quality.status}</span>
            {call.data_quality.detail && <span className="block text-xs text-muted-foreground">{call.data_quality.detail}</span>}
          </Field>
          {!call.trade && <Field label="Timeframes" testId="call-alignment">{call.alignment?.summary ?? "—"}</Field>}
        </div>
        {(call.reasons_for?.length || against.length) ? (
          <div className={cn("grid grid-cols-1 gap-3", !compact && "sm:grid-cols-2")}>
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-bull">Supports</div>
              <ul className="space-y-1 text-xs">{(call.reasons_for ?? []).slice(0, 4).map((r, i) => <li key={i} className="flex gap-1.5"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-bull" aria-hidden />{r}</li>)}</ul>
            </div>
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-bear">Against</div>
              <ul className="space-y-1 text-xs">{against.map((r, i) => <li key={i} className="flex gap-1.5"><XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-bear" aria-hidden />{r}</li>)}</ul>
            </div>
          </div>
        ) : null}
        {call.score != null && <p className="text-xs text-muted-foreground">Setup score {call.score}/100: {call.score_note}.</p>}
      </div>

      {call.trade && <div className="mt-3"><TradeManagementLine m={call.trade} p={p} /></div>}

      {call.hypothetical ? (
        <div className="mt-3 rounded-xl border-2 border-dashed border-warn/60 p-3 sm:p-4" data-testid="call-hypothetical">
          <div className="mb-2 flex items-center gap-2 text-sm font-bold text-warn"><FlaskConical className="h-4 w-4" aria-hidden />{call.hypothetical.label} · {call.hypothetical.direction}</div>
          <LevelsGrid lv={call.hypothetical} p={p} />
          <p className="mt-2 text-xs text-muted-foreground">{call.hypothetical.note}</p>
        </div>
      ) : unvalidated && call.decision === "WAIT" && call.wait_kind === "unvalidated" ? (
        <p className="mt-3 flex items-start gap-1.5 text-xs text-muted-foreground">
          <CircleSlash className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          Hypothetical entry, stop and targets are hidden because these rules are not validated. Turn on experimental analysis mode in
          {" "}<Link href="/settings" className="text-primary hover:underline">Settings</Link> to inspect them, clearly marked unvalidated.
        </p>
      ) : null}
      {call.decision === "ENTER" && (
        <p className="mt-3 flex items-start gap-1.5 text-xs text-muted-foreground"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />Analysis only: no order is placed. You decide and act in your own platform.</p>
      )}
    </section>
  );
}

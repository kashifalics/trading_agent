"use client";

// Active Trades: only what is in the market now. Two different things, kept apart and labelled:
// open trades of the simulated paper account (v1 rules forward test) and engine signals whose entry has triggered (hypothetical
// tracking, never orders). Pending orders and signals still waiting for entry are left out.

import { Briefcase, Zap } from "lucide-react";
import { EmptyState, PageHeader, QueryState } from "@/components/domain/common";
import { AnalysisOnlyNotice } from "@/components/domain/decision";
import { KpiTile } from "@/components/domain/overview";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { SignalRecord } from "@/lib/engine-types";
import { useEngineOpenSignals, useInstruments, usePaperTrades } from "@/lib/hooks";
import type { PaperTrade } from "@/lib/paper-types";
import { fmtPrice, fmtSignedR, timeAgo } from "@/lib/utils";

const IN_MARKET = ["ACTIVE", "TP1 HIT", "TP2 HIT"];

/** Hypothetical R of a tracked signal at its last price: (last - entry) in the trade's direction, over the entry-to-stop risk. */
function signalR(s: SignalRecord): number | null {
  const risk = s.risk ?? Math.abs(s.entry - s.stop_loss);
  if (s.last_price == null || !risk) return null;
  return ((s.last_price - s.entry) * (s.direction === "BUY" ? 1 : -1)) / risk;
}

function SideBadge({ side }: { side: "BUY" | "SELL" }) {
  return <Badge variant={side === "BUY" ? "buy" : "sell"}>{side}</Badge>;
}

function rClass(r: number | null | undefined) {
  return r == null ? "" : r > 0 ? "text-bull" : r < 0 ? "text-bear" : "";
}

function PaperTable({ trades, prec }: { trades: PaperTrade[]; prec: (s: string) => number }) {
  return (
    <Table>
      <THead>
        <TR>
          <TH>Instrument</TH><TH>TF</TH><TH>Side</TH><TH className="text-right">Fill</TH><TH className="text-right">Stop</TH>
          <TH className="text-right">Target</TH><TH className="text-right">Last</TH><TH className="text-right">R now</TH>
          <TH className="text-right">P&amp;L</TH><TH>Open for</TH><TH>Management</TH>
        </TR>
      </THead>
      <TBody>
        {trades.map((t) => {
          const p = prec(t.symbol);
          const m = t.management;
          return (
            <TR key={t.id} data-testid={`paper-${t.id}`}>
              <TD className="font-medium">{t.symbol}</TD>
              <TD>{t.timeframe}</TD>
              <TD><SideBadge side={t.direction} /></TD>
              <TD className="num text-right">{fmtPrice(t.fill_price ?? t.entry_price, p)}</TD>
              <TD className="num text-right">{fmtPrice(t.stop_loss, p)}</TD>
              <TD className="num text-right">{fmtPrice(t.take_profit, p)}</TD>
              <TD className="num text-right">{fmtPrice(t.last_price, p)}</TD>
              <TD className={`num text-right font-semibold ${rClass(t.unrealized_r)}`}>{fmtSignedR(t.unrealized_r)}</TD>
              <TD className={`num text-right ${rClass(t.unrealized_pnl)}`}>
                {t.unrealized_pnl == null ? "—" : `${t.unrealized_pnl >= 0 ? "+" : "-"}$${Math.abs(t.unrealized_pnl).toFixed(2)}`}
              </TD>
              <TD className="whitespace-nowrap text-xs text-muted-foreground">{timeAgo(t.filled_at)}</TD>
              <TD>
                {m ? (
                  <Badge variant={m.action === "EXIT" ? "sell" : m.action === "HOLD" ? "info" : "neutral"} title={m.reason}>{m.action}</Badge>
                ) : "—"}
              </TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}

function SignalTable({ signals, prec }: { signals: SignalRecord[]; prec: (s: string) => number }) {
  return (
    <Table>
      <THead>
        <TR>
          <TH>Instrument</TH><TH>TF</TH><TH>Strategy</TH><TH>Side</TH><TH className="text-right">Entry</TH><TH className="text-right">Stop</TH>
          <TH>TP1 / TP2 / TP3</TH><TH>Status</TH><TH className="text-right">Last</TH><TH className="text-right">R now</TH><TH>Active since</TH>
        </TR>
      </THead>
      <TBody>
        {signals.map((s) => {
          const p = prec(s.symbol);
          const r = signalR(s);
          const tps = [s.tp1, s.tp2, s.tp3];
          return (
            <TR key={s.id} data-testid={`sig-${s.id}`}>
              <TD className="font-medium">{s.symbol}</TD>
              <TD>{s.timeframe}</TD>
              <TD className="text-xs">{s.strategy_name ?? s.strategy}</TD>
              <TD><SideBadge side={s.direction} /></TD>
              <TD className="num text-right">{fmtPrice(s.entry, p)}</TD>
              <TD className="num text-right">{fmtPrice(s.stop_loss, p)}</TD>
              <TD className="num whitespace-nowrap text-xs">
                {tps.map((x, k) => (
                  <span key={k} className={s.best_target > k ? "font-semibold text-bull" : ""} title={s.best_target > k ? `TP${k + 1} hit` : undefined}>
                    {k > 0 ? " / " : ""}{fmtPrice(x, p)}{s.best_target > k ? " ✓" : ""}
                  </span>
                ))}
              </TD>
              <TD><Badge variant={s.status === "ACTIVE" ? "info" : "buy"}>{s.status}</Badge></TD>
              <TD className="num text-right">{fmtPrice(s.last_price, p)}</TD>
              <TD className={`num text-right font-semibold ${rClass(r)}`}>{fmtSignedR(r)}</TD>
              <TD className="whitespace-nowrap text-xs text-muted-foreground">{timeAgo(s.triggered_at ?? s.detected_at)}</TD>
            </TR>
          );
        })}
      </TBody>
    </Table>
  );
}

export default function ActiveTradesPage() {
  const paperQ = usePaperTrades("open");
  const sigQ = useEngineOpenSignals();
  const inst = useInstruments();
  const precisions = new Map((inst.data ?? []).map((i) => [i.canonical_symbol, i.price_precision]));
  const prec = (s: string) => precisions.get(s) ?? 2;
  const paper = (paperQ.data?.items ?? []).filter((t) => t.status === "open")
    .sort((a, b) => (b.filled_at ?? "").localeCompare(a.filled_at ?? ""));
  const signals = (sigQ.data?.items ?? []).filter((s) => IN_MARKET.includes(s.status));
  const openR = paper.reduce((sum, t) => sum + (t.unrealized_r ?? 0), 0);
  const count = (st: string) => signals.filter((s) => s.status === st).length;

  return (
    <>
      <PageHeader title="Active Trades"
        description="Only what is in the market right now: open trades of the simulated paper account, and engine signals whose entry has triggered. Pending orders and signals still waiting for entry are not listed. Refreshes automatically." />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="active-kpis">
        <KpiTile icon={Briefcase} tone="orange" label="Open paper trades" testId="kpi-active-paper"
          value={paperQ.isLoading ? "…" : paper.length} sub={paperQ.isLoading ? "loading" : `${fmtSignedR(openR)} unrealised in total`} />
        <KpiTile icon={Zap} tone="violet" label="Engine signals in the market" testId="kpi-active-signals"
          value={sigQ.isLoading ? "…" : signals.length}
          sub={sigQ.isLoading ? "loading" : `${count("ACTIVE")} active · ${count("TP1 HIT")} past TP1 · ${count("TP2 HIT")} past TP2`} />
      </div>

      <Card className="mt-4" data-testid="active-paper">
        <CardHeader><CardTitle>Paper trades</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs text-muted-foreground">
            The simulated paper account (forward test of the older v1 rules): simulated fills on live prices, no broker. HOLD / EXIT is the
            management call from the trade&apos;s own stop and target.
          </p>
          <QueryState query={paperQ} isEmpty={() => paper.length === 0} empty={<EmptyState title="No open paper trades" />}>
            {() => <PaperTable trades={paper} prec={prec} />}
          </QueryState>
        </CardContent>
      </Card>

      <Card className="mt-4" data-testid="active-signals">
        <CardHeader><CardTitle>Engine signals in the market</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Hypothetical tracking of the strategy engine&apos;s signals on 1-minute candles, entry triggered and not yet closed. Not orders and not
            paper trades. Research: no strategy is validated, so every plan is an UNVALIDATED — HYPOTHETICAL TRADE PLAN.
          </p>
          <QueryState query={sigQ} isEmpty={() => signals.length === 0} empty={<EmptyState title="No engine signal in the market" />}>
            {() => <SignalTable signals={signals} prec={prec} />}
          </QueryState>
        </CardContent>
      </Card>

      <div className="mt-4"><AnalysisOnlyNotice /></div>
    </>
  );
}

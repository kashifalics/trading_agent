"use client";

// Trade History: the paper account's closed trades with their result, newest close first (the last 50 / 100 / 200).
// R is after the spread for every trade; a dollar P&L exists only for trades the account took within its risk limits.

import { useState } from "react";
import { EmptyState, PageHeader, QueryState } from "@/components/domain/common";
import { AnalysisOnlyNotice } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useInstruments, usePaperTrades } from "@/lib/hooks";
import type { PaperTrade } from "@/lib/paper-types";
import { fmtDate, fmtPrice, fmtSignedR } from "@/lib/utils";

type Span = "50" | "100" | "200";
const SPANS: { id: Span; label: string }[] = [{ id: "50", label: "Last 50" }, { id: "100", label: "Last 100" }, { id: "200", label: "Last 200" }];

const usd = (v: number) => `${v >= 0 ? "+" : "-"}$${Math.abs(v).toFixed(2)}`;
const tone = (v: number | null | undefined) => (v == null ? "" : v > 0 ? "text-bull" : v < 0 ? "text-bear" : "");

/** "2d 3h", "1h 30m", "14m": from the fill to the close. */
function held(from: string | null, to: string | null): string {
  if (!from || !to) return "—";
  const m = Math.max(0, Math.round((new Date(to).getTime() - new Date(from).getTime()) / 60000));
  const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60;
  return d ? `${d}d ${h}h` : h ? `${h}h ${mm}m` : `${mm}m`;
}

function ResultBadge({ reason }: { reason: string | null }) {
  if (reason === "target") return <Badge variant="buy">TARGET</Badge>;
  if (reason === "stop") return <Badge variant="sell">STOP</Badge>;
  return <Badge>{(reason ?? "closed").replace(/_/g, " ").toUpperCase()}</Badge>;
}

function Summary({ trades }: { trades: PaperTrade[] }) {
  const r = trades.map((t) => t.r_net ?? 0);
  const wins = r.filter((x) => x > 0).length;
  const net = r.reduce((a, b) => a + b, 0);
  const acct = trades.filter((t) => t.pnl != null);
  const usdNet = acct.reduce((a, t) => a + (t.pnl ?? 0), 0);
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="history-summary">
      <div className="rounded-2xl border border-border/70 bg-card p-4 shadow-card">
        <div className="text-sm text-muted-foreground">Trades shown</div>
        <div className="num text-2xl font-bold">{trades.length} trades</div>
        <div className="text-xs text-muted-foreground">{wins} wins · {trades.length - wins} losses ({Math.round((100 * wins) / Math.max(trades.length, 1))}%)</div>
      </div>
      <div className="rounded-2xl border border-border/70 bg-card p-4 shadow-card">
        <div className="text-sm text-muted-foreground">Net result (after spread)</div>
        <div className={`num text-2xl font-bold ${tone(net)}`}>{fmtSignedR(net)}</div>
        <div className="text-xs text-muted-foreground">{fmtSignedR(trades.length ? net / trades.length : 0, 2)} per trade</div>
      </div>
      <div className="rounded-2xl border border-border/70 bg-card p-4 shadow-card">
        <div className="text-sm text-muted-foreground">Account P&amp;L</div>
        <div className={`num text-2xl font-bold ${tone(usdNet)}`}>{acct.length ? usd(usdNet) : "—"}</div>
        <div className="text-xs text-muted-foreground">{acct.length ? `${usd(usdNet)} on ${acct.length} account trades` : "no trade taken by the account"}</div>
      </div>
      <div className="rounded-2xl border border-border/70 bg-card p-4 shadow-card">
        <div className="text-sm text-muted-foreground">Range</div>
        <div className="num text-base font-semibold">best {fmtSignedR(r.length ? Math.max(...r) : null, 2)} · worst {fmtSignedR(r.length ? Math.min(...r) : null, 2)}</div>
      </div>
    </div>
  );
}

export default function TradeHistoryPage() {
  const q = usePaperTrades("closed");
  const inst = useInstruments();
  const [span, setSpan] = useState<Span>("100");
  const precisions = new Map((inst.data ?? []).map((i) => [i.canonical_symbol, i.price_precision]));
  const prec = (s: string) => precisions.get(s) ?? 2;
  const closed = (q.data?.items ?? []).filter((t) => t.status === "closed" && t.closed_at)
    .sort((a, b) => (b.closed_at ?? "").localeCompare(a.closed_at ?? ""));
  const shown = closed.slice(0, Number(span));
  // the running total starts at the oldest trade shown and ends at the newest
  const cum = new Map<number, number>();
  let run = 0;
  for (const t of [...shown].reverse()) {
    run += t.r_net ?? 0;
    cum.set(t.id, run);
  }

  return (
    <>
      <PageHeader title="Trade History"
        description="The paper account's closed trades, newest first, with their result after the spread. Refreshes automatically." />

      <QueryState query={q} isEmpty={() => closed.length === 0} empty={<EmptyState title="No closed paper trades yet" />}>
        {(d) => (
          <>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <Tabs tabs={SPANS} value={span} onChange={setSpan} />
              <span className="text-xs text-muted-foreground" data-testid="history-total">{d.total.toLocaleString()} closed in total</span>
            </div>
            <Summary trades={shown} />
            <Card className="mt-4" data-testid="history-table">
              <CardHeader><CardTitle>Closed trades</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  The simulated paper account (forward test of the older v1 rules): simulated fills on live prices, no broker. R is after the
                  spread. A dollar P&amp;L exists only for trades the account took within its risk limits; the others were tracked, not taken.
                </p>
                <Table>
                  <THead>
                    <TR>
                      <TH>Closed</TH><TH>Instrument</TH><TH>TF</TH><TH>Side</TH><TH className="text-right">Fill</TH><TH className="text-right">Exit</TH>
                      <TH>Result</TH><TH className="text-right">R</TH><TH className="text-right">P&amp;L</TH><TH className="text-right">Running R</TH><TH>Held</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {shown.map((t) => {
                      const p = prec(t.symbol);
                      return (
                        <TR key={t.id} data-testid={`hist-${t.id}`}>
                          <TD className="whitespace-nowrap text-xs">{fmtDate(t.closed_at)}</TD>
                          <TD className="font-medium">{t.symbol}</TD>
                          <TD>{t.timeframe}</TD>
                          <TD><Badge variant={t.direction === "BUY" ? "buy" : "sell"}>{t.direction}</Badge></TD>
                          <TD className="num text-right">{fmtPrice(t.fill_price ?? t.entry_price, p)}</TD>
                          <TD className="num text-right">{fmtPrice(t.exit_price, p)}</TD>
                          <TD><ResultBadge reason={t.exit_reason} /></TD>
                          <TD className={`num text-right font-semibold ${tone(t.r_net)}`}>{fmtSignedR(t.r_net, 2)}</TD>
                          <TD className={`num text-right ${tone(t.pnl)}`} data-testid={`pnl-${t.id}`}
                            title={t.pnl == null ? "not taken by the account (its risk limits were full): tracked for the forward test only" : undefined}>
                            {t.pnl == null ? "—" : usd(t.pnl)}
                          </TD>
                          <TD className={`num text-right ${tone(cum.get(t.id))}`} data-testid={`cum-${t.id}`}>{fmtSignedR(cum.get(t.id))}</TD>
                          <TD className="whitespace-nowrap text-xs text-muted-foreground">{held(t.filled_at, t.closed_at)}</TD>
                        </TR>
                      );
                    })}
                  </TBody>
                </Table>
              </CardContent>
            </Card>
          </>
        )}
      </QueryState>

      <div className="mt-4"><AnalysisOnlyNotice /></div>
    </>
  );
}

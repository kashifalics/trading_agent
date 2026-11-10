"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FlaskConical } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { SeriesChart } from "@/components/charts/series-chart";
import { EmptyState, ErrorState, InstrumentSelect, JobBadge, PageHeader, QueryState, TimeframeSelect } from "@/components/domain/common";
import { SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, Stat } from "@/components/ui/card";
import { FieldError, Input, Label, Select } from "@/components/ui/form";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useBacktest, useBacktests, useRunBacktest, useStrategies } from "@/lib/hooks";
import { backtestSchema, type BacktestForm } from "@/lib/schemas";
import { useSettings } from "@/lib/store";
import { fmtDate, fmtNum, fmtPct, fmtPrice, signClass } from "@/lib/utils";

const num = (m: Record<string, unknown> | null, k: string): number | null => (m && typeof m[k] === "number" ? (m[k] as number) : null);

export default function BacktestingPage() {
  const s = useSettings();
  const strategies = useStrategies();
  const runs = useBacktests();
  const run = useRunBacktest();
  const [id, setId] = useState<number | null>(null);
  const bt = useBacktest(id);
  const form = useForm<BacktestForm>({
    resolver: zodResolver(backtestSchema),
    values: { symbol: s.symbol, timeframe: s.timeframe, strategy: "decision_engine", bars: 3000, risk_pct: 1, spread: 0, slippage: 0, commission_pct: 0, eval_every: 2 },
  });
  const { errors } = form.formState;

  const b = bt.data;
  const m = b?.metrics ?? null;
  const equity = useMemo(() => (b?.equity_curve ?? []).map(([t, v]) => ({ time: Math.floor(new Date(t).getTime() / 1000), value: v })), [b]);
  const drawdown = useMemo(() => {
    let peak = -Infinity;
    return equity.map((p) => { peak = Math.max(peak, p.value); return { time: p.time, value: -((peak - p.value) / peak) * 100 }; });
  }, [equity]);

  const submit = form.handleSubmit((v) => run.mutate({ ...v, auto_sync: true }, { onSuccess: (j) => setId(j.id) }));
  const active = b && (b.status === "queued" || b.status === "running");

  return (
    <>
      <PageHeader title="Backtesting" description="Event-driven simulation with spread, slippage, commission and risk-based sizing. Entries fill at the next bar's open; if a bar contains both stop and target, the stop is assumed hit first." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="space-y-4">
          <SectionCard title="Strategy configuration">
            <form onSubmit={submit} className="space-y-3" aria-label="Backtest configuration">
              <div className="grid grid-cols-2 gap-3">
                <div><Label htmlFor="b-sym">Instrument</Label><InstrumentSelect id="b-sym" onlySupported value={s.symbol} onChange={(v) => s.set({ symbol: v })} /></div>
                <div><Label htmlFor="b-tf">Timeframe</Label><TimeframeSelect id="b-tf" value={s.timeframe} onChange={(v) => s.set({ timeframe: v })} /></div>
              </div>
              <div><Label htmlFor="b-strat">Strategy</Label>
                <Select id="b-strat" {...form.register("strategy")}>
                  {(strategies.data ?? [{ id: "decision_engine", description: "" }]).map((x) => <option key={x.id} value={x.id}>{x.id}</option>)}
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {([["bars", "Bars"], ["risk_pct", "Risk per trade %"], ["spread", "Spread (price units)"], ["slippage", "Slippage (price units)"], ["commission_pct", "Commission % / side"], ["eval_every", "Evaluate every N bars"]] as const).map(([k, label]) => (
                  <div key={k}><Label htmlFor={`b-${k}`}>{label}</Label><Input id={`b-${k}`} inputMode="decimal" {...form.register(k)} /><FieldError message={errors[k]?.message} /></div>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground">Date range = the most recent N stored bars of the selected series.</p>
              <Button type="submit" loading={run.isPending || !!active} className="w-full"><FlaskConical className="h-4 w-4" /> Run backtest</Button>
              {run.isError && <ErrorState error={run.error} />}
            </form>
          </SectionCard>
          <SectionCard title="Previous runs">
            <QueryState query={runs} isEmpty={(d) => d.items.length === 0} empty={<p className="text-sm text-muted-foreground">No backtests yet.</p>}>
              {(d) => (
                <ul className="space-y-1">
                  {d.items.map((r) => (
                    <li key={r.id}>
                      <button onClick={() => setId(r.id)} className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm hover:bg-muted ${r.id === id ? "bg-muted" : ""}`}>
                        <span>#{r.id} {r.symbol} {r.timeframe} · {r.strategy}</span><JobBadge status={r.status} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </QueryState>
          </SectionCard>
        </div>

        <div className="min-w-0 space-y-4">
          {!id && <EmptyState title="No backtest selected" hint="Configure a strategy and run it, or pick a previous run." />}
          {bt.isError && <ErrorState error={bt.error} onRetry={() => void bt.refetch()} />}
          {active && <Card><CardContent role="status" className="text-sm text-muted-foreground">Backtest {b?.status}… this can take a minute for the decision-engine strategy.</CardContent></Card>}
          {b?.status === "failed" && <p role="alert" className="rounded border border-bear/30 bg-bear/5 p-3 text-sm text-bear">{b.error}</p>}
          {b?.status === "completed" && m && (
            <>
              <Card>
                <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4" data-testid="bt-metrics">
                  <Stat label="Total return" value={<span className={signClass(num(m, "total_return_pct"))}>{fmtNum(num(m, "total_return_pct"), 2)}%</span>} />
                  <Stat label="Trades" value={fmtNum(num(m, "n_trades"), 0)} sub={`${fmtPct(num(m, "win_rate"))} win rate`} />
                  <Stat label="Profit factor" value={fmtNum(num(m, "profit_factor"), 2)} />
                  <Stat label="Expectancy (R)" value={fmtNum(num(m, "expectancy_r"), 2)} sub={Array.isArray(m.expectancy_r_ci) ? `95% CI ${fmtNum(m.expectancy_r_ci[0] as number, 2)} … ${fmtNum(m.expectancy_r_ci[1] as number, 2)}` : undefined} />
                  <Stat label="Max drawdown" value={`${fmtNum(num(m, "max_drawdown_pct"), 1)}%`} />
                  <Stat label="Sharpe (ann.)" value={fmtNum(num(m, "sharpe_annualized"), 2)} />
                  <Stat label="Costs paid" value={fmtNum(num(m, "total_costs"), 0)} />
                  <Stat label="Exposure" value={`${fmtNum(num(m, "exposure_pct"), 0)}%`} />
                </CardContent>
              </Card>
              {num(m, "n_trades") === 0 && <p className="text-sm text-muted-foreground">No trades were generated in this window.</p>}
              <SectionCard title="Equity curve"><SeriesChart data={equity} color="#4f9bf7" kind="area" label="Equity curve" /></SectionCard>
              <SectionCard title="Drawdown (%)"><SeriesChart data={drawdown} color="#ef5b64" kind="area" height={150} label="Drawdown" /></SectionCard>
              <SectionCard title={`Trade history (${b.trades.length})`}>
                <div className="max-h-96 overflow-auto">
                  <Table>
                    <THead><TR><TH>Entry</TH><TH>Dir</TH><TH className="text-right">Entry px</TH><TH className="text-right">Exit px</TH><TH>Exit</TH><TH className="text-right">P&L</TH><TH className="text-right">R</TH></TR></THead>
                    <TBody>
                      {b.trades.map((t, i) => (
                        <TR key={i}>
                          <TD className="num whitespace-nowrap">{fmtDate(t.entry_ts)}</TD>
                          <TD><Badge variant={t.direction === "BUY" ? "buy" : "sell"}>{t.direction}</Badge></TD>
                          <TD className="num text-right">{fmtPrice(t.entry_price)}</TD><TD className="num text-right">{fmtPrice(t.exit_price)}</TD>
                          <TD className="text-muted-foreground">{t.exit_reason}</TD>
                          <TD className={`num text-right ${signClass(t.pnl)}`}>{fmtNum(t.pnl, 2)}</TD>
                          <TD className={`num text-right ${signClass(t.r_multiple)}`}>{fmtNum(t.r_multiple, 2)}</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </div>
              </SectionCard>
              {Array.isArray(m.caveats) && <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">{(m.caveats as string[]).map((c) => <li key={c}>{c}</li>)}</ul>}
            </>
          )}
        </div>
      </div>
    </>
  );
}

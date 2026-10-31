"use client";

import { EmptyState, JobBadge, PageHeader, QueryState } from "@/components/domain/common";
import { SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Stat } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useBacktests, useModels, usePredictionStats } from "@/lib/hooks";
import { fmtNum, fmtPct, signClass } from "@/lib/utils";

function Bars({ data }: { data: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(data));
  return (
    <ul className="space-y-1.5">
      {Object.entries(data).map(([k, v]) => (
        <li key={k} className="grid grid-cols-[110px_1fr_40px] items-center gap-2 text-sm">
          <span className="text-muted-foreground">{k.replace(/_/g, " ")}</span>
          <div className="h-2 rounded bg-muted"><div className="h-2 rounded bg-primary" style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="num text-right">{v}</span>
        </li>
      ))}
    </ul>
  );
}

export default function PerformancePage() {
  const stats = usePredictionStats();
  const backtests = useBacktests();
  const models = useModels();

  return (
    <>
      <PageHeader title="Performance Analytics" description="Tracked prediction outcomes, backtest results and out-of-sample model metrics. Small samples are not evidence of edge." />
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Prediction outcomes">
          <QueryState query={stats} isEmpty={(d) => d.total === 0} empty={<EmptyState title="No predictions tracked yet" hint="Outcomes appear after analyses produce BUY/SELL plans and later candles resolve them." />}>
            {(d) => (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <Stat label="Predictions" value={d.total} />
                  <Stat label="Resolved (TP/SL)" value={d.resolved} />
                  <Stat label="TP-first rate" value={d.tp_first_rate === null ? "—" : fmtPct(d.tp_first_rate)} sub={d.tp_first_ci ? `95% CI ${fmtPct(d.tp_first_ci[0])}–${fmtPct(d.tp_first_ci[1])}` : "needs resolved trades"} />
                </div>
                {d.resolved < 30 && d.resolved > 0 && <p className="text-xs text-warn">Only {d.resolved} resolved — the interval above is very wide.</p>}
                <div className="grid gap-4 sm:grid-cols-2">
                  <div><h4 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">By decision</h4><Bars data={d.by_decision} /></div>
                  <div><h4 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">By outcome</h4><Bars data={d.by_outcome} /></div>
                </div>
                <Table>
                  <THead><TR><TH>Instrument</TH><TH className="text-right">Total</TH><TH className="text-right">BUY</TH><TH className="text-right">SELL</TH><TH className="text-right">WAIT</TH><TH className="text-right">TP/SL</TH><TH className="text-right">Avg R</TH></TR></THead>
                  <TBody>
                    {Object.entries(d.per_instrument).map(([sym, v]) => (
                      <TR key={sym}><TD className="font-medium">{sym}</TD><TD className="num text-right">{v.total}</TD><TD className="num text-right">{v.BUY}</TD><TD className="num text-right">{v.SELL}</TD><TD className="num text-right">{v.WAIT}</TD><TD className="num text-right">{v.tp_hit}/{v.sl_hit}</TD><TD className={`num text-right ${signClass(v.avg_r)}`}>{fmtNum(v.avg_r, 2)}</TD></TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            )}
          </QueryState>
        </SectionCard>

        <SectionCard title="Backtest runs">
          <QueryState query={backtests} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No backtests yet" />}>
            {(d) => (
              <Table>
                <THead><TR><TH>Run</TH><TH>Status</TH><TH className="text-right">Trades</TH><TH className="text-right">Return</TH><TH className="text-right">PF</TH><TH className="text-right">Max DD</TH></TR></THead>
                <TBody>
                  {d.items.map((r) => {
                    const m = r.metrics ?? {};
                    const n = (k: string) => (typeof m[k] === "number" ? (m[k] as number) : null);
                    return (
                      <TR key={r.id}>
                        <TD>#{r.id} {r.symbol} {r.timeframe}<div className="text-xs text-muted-foreground">{r.strategy}</div></TD>
                        <TD><JobBadge status={r.status} /></TD>
                        <TD className="num text-right">{fmtNum(n("n_trades"), 0)}</TD>
                        <TD className={`num text-right ${signClass(n("total_return_pct"))}`}>{n("total_return_pct") === null ? "—" : `${fmtNum(n("total_return_pct"), 1)}%`}</TD>
                        <TD className="num text-right">{fmtNum(n("profit_factor"), 2)}</TD>
                        <TD className="num text-right">{n("max_drawdown_pct") === null ? "—" : `${fmtNum(n("max_drawdown_pct"), 1)}%`}</TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
            )}
          </QueryState>
        </SectionCard>

        <div className="lg:col-span-2">
          <SectionCard title="Out-of-sample model metrics (walk-forward)">
            <QueryState query={models} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No models trained" hint="Train one from the Models page." />}>
              {(d) => (
                <Table>
                  <THead><TR><TH>Model</TH><TH>Status</TH><TH className="text-right">OOS rows</TH><TH className="text-right">OOS trades</TH><TH className="text-right">Expectancy (R)</TH><TH className="text-right">Brier skill</TH><TH className="text-right">Coverage</TH></TR></THead>
                  <TBody>
                    {d.items.map((m) => (
                      <TR key={m.id}>
                        <TD>{m.name}</TD>
                        <TD><Badge variant={m.validation_status === "passed_minimum_checks" ? "buy" : "wait"}>{m.validation_status.replace(/_/g, " ")}</Badge></TD>
                        <TD className="num text-right">{m.summary.n_oos_rows ?? "—"}</TD>
                        <TD className="num text-right">{m.oos_trades?.n_trades ?? "—"}</TD>
                        <TD className={`num text-right ${signClass(m.oos_trades?.expectancy_r as number | null)}`}>{fmtNum(m.oos_trades?.expectancy_r as number | null, 2)}</TD>
                        <TD className={`num text-right ${signClass(m.summary.brier_skill)}`}>{fmtNum(m.summary.brier_skill, 3)}</TD>
                        <TD className="num text-right">{fmtPct(m.summary.prediction_coverage, 1)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </QueryState>
          </SectionCard>
        </div>
      </div>
    </>
  );
}

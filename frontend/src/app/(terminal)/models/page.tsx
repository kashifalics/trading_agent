"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Brain } from "lucide-react";
import { useForm } from "react-hook-form";
import { EmptyState, ErrorState, InstrumentSelect, PageHeader, QueryState, TimeframeSelect } from "@/components/domain/common";
import { SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Stat } from "@/components/ui/card";
import { FieldError, Input, Label, Select } from "@/components/ui/form";
import { useActivateModel, useModels, useTrainModel } from "@/lib/hooks";
import { trainSchema, type TrainForm } from "@/lib/schemas";
import { useSettings } from "@/lib/store";
import { fmtDate, fmtNum, fmtPct, signClass } from "@/lib/utils";

export default function ModelsPage() {
  const s = useSettings();
  const models = useModels();
  const train = useTrainModel();
  const activate = useActivateModel();
  const form = useForm<TrainForm>({
    resolver: zodResolver(trainSchema),
    values: { symbol: s.symbol, timeframe: s.timeframe, algorithm: "logistic", bars: 20000, spread: 0, horizon_bars: 24 },
  });
  const { errors } = form.formState;

  return (
    <>
      <PageHeader title="Model Management" description="Chronological, purged walk-forward training with out-of-time probability calibration. A model is “research only” unless it passes minimum out-of-sample checks — and even then, no performance is guaranteed." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
        <SectionCard title="Train a model">
          <form onSubmit={form.handleSubmit((v) => train.mutate({ ...v, n_splits: 5, auto_sync: true }))} className="space-y-3" aria-label="Train model">
            <div className="grid grid-cols-2 gap-3">
              <div><Label htmlFor="m-sym">Instrument</Label><InstrumentSelect id="m-sym" onlySupported value={s.symbol} onChange={(v) => s.set({ symbol: v })} /></div>
              <div><Label htmlFor="m-tf">Timeframe</Label><TimeframeSelect id="m-tf" value={s.timeframe} onChange={(v) => s.set({ timeframe: v })} /></div>
            </div>
            <div><Label htmlFor="m-algo">Algorithm</Label>
              <Select id="m-algo" {...form.register("algorithm")}><option value="logistic">Logistic regression (baseline)</option><option value="lightgbm">LightGBM</option><option value="xgboost">XGBoost</option></Select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {([["bars", "Bars"], ["horizon_bars", "Horizon"], ["spread", "Spread"]] as const).map(([k, l]) => (
                <div key={k}><Label htmlFor={`m-${k}`}>{l}</Label><Input id={`m-${k}`} inputMode="decimal" {...form.register(k)} /><FieldError message={errors[k]?.message} /></div>
              ))}
            </div>
            <Button type="submit" className="w-full" loading={train.isPending}><Brain className="h-4 w-4" /> Train in background</Button>
            {train.isSuccess && <p role="status" className="text-xs text-muted-foreground">{train.data.note}</p>}
            {train.isError && <ErrorState error={train.error} />}
          </form>
        </SectionCard>

        <div className="space-y-4">
          <QueryState query={models} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No models yet" hint="Without a model, decisions rely on price-action evidence and historical analogues only." />}>
            {(d) => (
              <>
                {d.items.map((m) => (
                  <Card key={m.id}>
                    <CardHeader>
                      <CardTitle>{m.name} <span className="ml-2 font-normal text-muted-foreground">v{m.version}</span></CardTitle>
                      <div className="flex items-center gap-2">
                        {m.is_active && <Badge variant="info">active</Badge>}
                        <Badge variant={m.validation_status === "passed_minimum_checks" ? "buy" : "wait"}>{m.validation_status.replace(/_/g, " ")}</Badge>
                        {!m.is_active && (m.validation_status === "passed_minimum_checks" && m.is_calibrated
                          ? <Button size="sm" variant="outline" loading={activate.isPending} onClick={() => activate.mutate(m.id)}>Activate</Button>
                          : <span className="text-[11px] text-muted-foreground" title="Only a calibrated model that passed the out-of-sample checks can be activated">not activatable</span>)}
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                        <Stat label="Samples" value={m.n_samples} />
                        <Stat label="OOS rows" value={m.summary.n_oos_rows ?? "—"} />
                        <Stat label="OOS trades" value={m.oos_trades?.n_trades ?? "—"} />
                        <Stat label="Expectancy R" value={<span className={signClass(m.oos_trades?.expectancy_r as number | null)}>{fmtNum(m.oos_trades?.expectancy_r as number | null, 2)}</span>} />
                        <Stat label="Brier skill" value={<span className={signClass(m.summary.brier_skill)}>{fmtNum(m.summary.brier_skill, 3)}</span>} sub={`coverage ${fmtPct(m.summary.prediction_coverage, 1)}`} />
                      </div>
                      {m.validation_reasons && m.validation_reasons.length > 0 && (
                        <div>
                          <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Why it is not validated</div>
                          <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{m.validation_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                        </div>
                      )}
                      {m.summary.error && <p className="text-xs text-warn">{m.summary.error}</p>}
                      <p className="text-[11px] text-muted-foreground">Trained {fmtDate(m.trained_at)} · {m.algorithm} · {m.symbol} {m.timeframe} · calibrated: {m.is_calibrated ? "yes" : "no"}</p>
                    </CardContent>
                  </Card>
                ))}
              </>
            )}
          </QueryState>
        </div>
      </div>
    </>
  );
}

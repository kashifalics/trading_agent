"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Download, Play, Upload } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { CandleChart } from "@/components/charts/candle-chart";
import { buildMarkers, buildPlanLines, buildStructure, buildZones } from "@/components/charts/overlay-build";
import { ChartLegend } from "@/components/charts/legend";
import { EmptyState, ErrorState, InstrumentSelect, JobBadge, PageHeader, SourceNote, TimeframeSelect } from "@/components/domain/common";
import { CallCard } from "@/components/domain/call";
import { AnalysisOnlyNotice, ConfidencePanelView, EvidenceList, PlanCard, SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox, FieldError, Input, Label } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { useAnalysis, useCandles, useInstruments, usePredictions, useRunAnalysis, useSync, useUploadChart } from "@/lib/hooks";
import { analysisSchema, uploadSchema, type AnalysisForm, type UploadForm } from "@/lib/schemas";
import { useSettings, type OverlayToggles } from "@/lib/store";
import type { ChartAnalyzeResult } from "@/lib/types";
import { fmtDate } from "@/lib/utils";

const RECENT = 180; // overlays and the initial view cover the most recent bars
const TOGGLES: [keyof OverlayToggles, string][] = [
  ["swings", "Swings"], ["structure", "BOS / CHoCH"], ["zones", "FVG / OB / S&D"], ["liquidity", "Liquidity"], ["patterns", "Candle patterns"], ["plan", "Entry / SL / TP"],
];

function UploadCard() {
  const upload = useUploadChart();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ChartAnalyzeResult | null>(null);
  const form = useForm<UploadForm>({ resolver: zodResolver(uploadSchema), defaultValues: { symbol: "", timeframe: "" } });
  const { errors } = form.formState;

  const submit = form.handleSubmit((v) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    if (v.symbol) fd.append("symbol", v.symbol);
    if (v.timeframe) fd.append("timeframe", v.timeframe);
    if (v.y1 !== undefined && v.y2 !== undefined) {
      fd.append("calibration_points", JSON.stringify([{ y: v.y1, price: v.p1 }, { y: v.y2, price: v.p2 }]));
    }
    upload.mutate(fd, { onSuccess: setResult });
  });

  return (
    <SectionCard title="Screenshot analysis">
      <form onSubmit={submit} className="space-y-3" aria-label="Screenshot upload">
        <div>
          <Label htmlFor="shot">Chart image (PNG / JPEG / WebP, ≤ 8 MB)</Label>
          <Input id="shot" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label htmlFor="u-sym">Instrument (optional)</Label><Input id="u-sym" placeholder="auto-detect from image" {...form.register("symbol")} /></div>
          <div><Label htmlFor="u-tf">Timeframe (optional)</Label><Input id="u-tf" placeholder="auto-detect, e.g. 1H" {...form.register("timeframe")} /></div>
        </div>
        <div>
          <Label>Price calibration (optional): two pixel rows and the price at each</Label>
          <div className="grid grid-cols-4 gap-2">
            <Input aria-label="Row 1 (px)" placeholder="row px" inputMode="decimal" {...form.register("y1")} />
            <Input aria-label="Price 1" placeholder="price" inputMode="decimal" {...form.register("p1")} />
            <Input aria-label="Row 2 (px)" placeholder="row px" inputMode="decimal" {...form.register("y2")} />
            <Input aria-label="Price 2" placeholder="price" inputMode="decimal" {...form.register("p2")} />
          </div>
          <FieldError message={errors.y1?.message ?? errors.y2?.message ?? errors.timeframe?.message} />
        </div>
        <SourceNote>Leave instrument and timeframe empty to read them from the chart title (e.g. XAUUSD 1H). Without OCR or calibration points, prices are not extracted and no entry/stop/target is produced. OHLC values are never guessed.</SourceNote>
        <Button type="submit" loading={upload.isPending} disabled={!file}><Upload className="h-4 w-4" /> Analyse screenshot</Button>
        {upload.isError && <ErrorState error={upload.error} />}
      </form>
      {result && (
        <div className="mt-4 space-y-2 border-t pt-3 text-sm" data-testid="upload-result">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={result.status === "analysed" ? "buy" : "wait"}>{result.status.replace("_", " ")}</Badge>
            <span>{result.n_candles} candles · quality {result.quality.score.toFixed(2)} · prices {result.price_calibrated ? "calibrated" : "not calibrated"}</span>
            {result.prediction_id && <Link className="text-primary hover:underline" href={`/predictions/${result.prediction_id}`}>Open prediction</Link>}
          </div>
          <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
            {result.warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        </div>
      )}
    </SectionCard>
  );
}

export default function ChartPage() {
  const s = useSettings();
  const instruments = useInstruments();
  const [jobId, setJobId] = useState<number | null>(null);
  const [useMtf, setUseMtf] = useState(true);
  const inst = instruments.data?.find((i) => i.canonical_symbol === s.symbol);
  const candles = useCandles(s.symbol, s.timeframe, 700, inst?.supported ?? true);
  const latest = usePredictions({ symbol: s.symbol, limit: 10 });
  const latestMatch = latest.data?.items.find((p) => p.timeframe === s.timeframe);
  const analysisId = jobId ?? latestMatch?.analysis_id ?? null;
  const analysis = useAnalysis(analysisId);
  const run = useRunAnalysis();
  const sync = useSync();

  const form = useForm<AnalysisForm>({
    resolver: zodResolver(analysisSchema),
    values: { symbol: s.symbol, timeframe: s.timeframe, higher: s.mtfHigher, intermediate: s.mtfIntermediate, entry: s.mtfEntry, lookback_bars: 1500, auto_sync: true },
  });

  const result = analysis.data?.status === "completed" ? analysis.data.result : null;
  const precision = candles.data?.price_precision ?? inst?.price_precision ?? 2;
  const cs = candles.data?.candles ?? [];
  const firstVisible = cs.length > RECENT ? cs[cs.length - RECENT].time : (cs[0]?.time ?? 0);
  const lastTs = cs.length ? cs[cs.length - 1].time : 0;
  const barSeconds = cs.length > 1 ? cs[1].time - cs[0].time : 0;
  const detail = s.chartDetail;
  const markers = useMemo(() => (result ? buildMarkers(result.events, result.swings, s.overlays, firstVisible, detail, lastTs, barSeconds) : []), [result, s.overlays, firstVisible, detail, lastTs, barSeconds]);
  const zones = useMemo(() => (result ? buildZones(result.events, s.overlays, firstVisible, { price: result.last_close, atr: result.atr }, detail) : []), [result, s.overlays, firstVisible, detail]);
  const segments = useMemo(() => (result ? buildStructure(result.events, s.overlays, firstVisible, detail) : []), [result, s.overlays, firstVisible, detail]);
  // entry/stop/target lines only when the backend call provides levels (ENTER) or hypothetical ones (experimental mode)
  const showPlan = !!(analysis.data?.call?.levels || analysis.data?.call?.hypothetical);
  const lines = useMemo(() => buildPlanLines(showPlan ? result?.decision.plan ?? null : null, s.overlays), [result, s.overlays, showPlan]);
  const resultMatchesChart = analysis.data?.symbol === s.symbol && analysis.data?.timeframe === s.timeframe;

  const onRun = form.handleSubmit((v) => {
    run.mutate(
      { symbol: v.symbol, timeframe: v.timeframe, mtf: useMtf ? { higher: v.higher || undefined, intermediate: v.intermediate || undefined, entry: v.entry || undefined } : {}, lookback_bars: v.lookback_bars, auto_sync: v.auto_sync },
      { onSuccess: (j) => setJobId(j.id) },
    );
  });

  const jobActive = analysis.data && (analysis.data.status === "queued" || analysis.data.status === "running");

  return (
    <>
      <PageHeader title="Chart Analysis" description="Candles come from your own backend store. Run an analysis to overlay structure, zones and a trade plan — or WAIT, when the evidence does not justify one." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-4">
          <Card>
            <CardContent>
              <form onSubmit={onRun} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_auto]" aria-label="Analysis controls">
                <div><Label htmlFor="sym">Instrument</Label><InstrumentSelect id="sym" value={s.symbol} onChange={(v) => s.set({ symbol: v })} /></div>
                <div><Label htmlFor="tf">Timeframe</Label><TimeframeSelect id="tf" value={s.timeframe} onChange={(v) => s.set({ timeframe: v })} /></div>
                <div><Label htmlFor="lb">Lookback bars</Label><Input id="lb" inputMode="numeric" {...form.register("lookback_bars")} /><FieldError message={form.formState.errors.lookback_bars?.message} /></div>
                <div className="flex flex-wrap items-end gap-2">
                  <Button type="submit" loading={run.isPending || !!jobActive} disabled={inst ? !inst.supported : false}><Play className="h-4 w-4" /> Run analysis</Button>
                  <Button type="button" variant="outline" loading={sync.isPending} disabled={inst ? !inst.supported : false} onClick={() => sync.mutate({ symbol: s.symbol, timeframe: s.timeframe, bars: 1500 })}><Download className="h-4 w-4" /> Sync</Button>
                </div>
                <div className="sm:col-span-2 lg:col-span-4">
                  <Checkbox label="Multi-timeframe analysis (completed higher-timeframe candles only)" checked={useMtf} onChange={(e) => setUseMtf(e.target.checked)} />
                  {useMtf && (
                    <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
                      <div><Label>Higher-TF trend</Label><TimeframeSelect allowNone label="Higher timeframe" value={s.mtfHigher} onChange={(v) => { s.set({ mtfHigher: v }); form.setValue("higher", v); }} /></div>
                      <div><Label>Intermediate structure</Label><TimeframeSelect allowNone label="Intermediate timeframe" value={s.mtfIntermediate} onChange={(v) => { s.set({ mtfIntermediate: v }); form.setValue("intermediate", v); }} /></div>
                      <div><Label>Entry timeframe</Label><TimeframeSelect allowNone label="Entry timeframe" value={s.mtfEntry} onChange={(v) => { s.set({ mtfEntry: v }); form.setValue("entry", v); }} /></div>
                    </div>
                  )}
                </div>
              </form>
              {inst && !inst.supported && <p className="mt-3 text-sm text-warn">{inst.canonical_symbol} has no configured data source: {inst.mappings[0]?.notes}</p>}
              {run.isError && <div className="mt-3"><ErrorState error={run.error} /></div>}
              {sync.isError && <div className="mt-3"><ErrorState error={sync.error} /></div>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{s.symbol} · {s.timeframe} <span className="ml-2 font-normal text-muted-foreground">{candles.data ? `${candles.data.provider} · ${candles.data.count} candles` : ""}</span></CardTitle>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <div role="group" aria-label="Chart detail" className="mr-2 inline-flex overflow-hidden rounded-lg border">
                  {(["clean", "detailed"] as const).map((d) => (
                    <button key={d} type="button" aria-pressed={detail === d} onClick={() => s.set({ chartDetail: d })}
                      className={`px-3 py-1 text-xs font-medium capitalize ${detail === d ? "bg-nav text-nav-foreground" : "text-muted-foreground hover:bg-muted"}`}>{d}</button>
                  ))}
                </div>
                {TOGGLES.map(([k, label]) => <Checkbox key={k} label={label} checked={s.overlays[k]} onChange={(e) => s.setOverlay(k, e.target.checked)} />)}
              </div>
            </CardHeader>
            <CardContent>
              {candles.isLoading ? <Skeleton className="h-[520px]" /> : candles.isError ? (
                <ErrorState error={candles.error} onRetry={() => void candles.refetch()} />
              ) : candles.data && candles.data.count === 0 ? (
                <EmptyState title="No stored candles for this selection" hint="Use Sync to download candles from the provider, or run an analysis with auto-sync enabled." />
              ) : (
                <CandleChart candles={candles.data?.candles ?? []} precision={precision} resetKey={`${s.symbol}${s.timeframe}`}
                  markers={resultMatchesChart ? markers : []} zones={resultMatchesChart ? zones : []} segments={resultMatchesChart ? segments : []} lines={resultMatchesChart ? lines : []} />
              )}
              {result && resultMatchesChart && <ChartLegend detail={detail} counts={{ zones: zones.length, structure: segments.length, markers: markers.length }} />}
              {result && !resultMatchesChart && <SourceNote>Overlays are hidden because the loaded analysis is for a different instrument/timeframe.</SourceNote>}
            </CardContent>
          </Card>

          {result && resultMatchesChart && <SectionCard title="Confidence — five separate views"><ConfidencePanelView panel={result.decision.confidence} /></SectionCard>}
          <UploadCard />
        </div>

        <aside className="space-y-4" aria-label="Analysis result">
          <Card>
            <CardHeader>
              <CardTitle>Decision</CardTitle>
              {analysis.data && <JobBadge status={analysis.data.status} />}
            </CardHeader>
            <CardContent className="space-y-3" data-testid="decision-panel">
              {!analysisId && <EmptyState title="No analysis yet" hint="Run an analysis to get a decision (ENTER, WAIT or NO TRADE) with its evidence." />}
              {jobActive && <div role="status" className="space-y-2 text-sm text-muted-foreground"><Skeleton className="h-2 w-full" />Analysis {analysis.data?.status}…</div>}
              {analysis.isError && <ErrorState error={analysis.error} onRetry={() => void analysis.refetch()} />}
              {analysis.data?.status === "failed" && <p role="alert" className="text-sm text-bear">{analysis.data.error}</p>}
              {result && (
                <>
                  <div className="text-xs text-muted-foreground">{analysis.data?.symbol} · {analysis.data?.timeframe} · as of {fmtDate(analysis.data?.as_of_ts)}</div>
                  {analysis.data?.call && <CallCard call={analysis.data.call} symbol={analysis.data.symbol ?? ""} precision={precision} />}
                  {(analysis.data?.call?.levels || analysis.data?.call?.hypothetical) && (
                    <div data-testid="hypothetical-plan">
                      {analysis.data?.call?.hypothetical && <p className="mb-1 text-xs font-semibold text-warn">HYPOTHETICAL — UNVALIDATED plan</p>}
                      <PlanCard decision={result.decision.decision} plan={result.decision.plan} precision={precision} waitReasons={result.decision.wait_reasons} />
                    </div>
                  )}
                  <pre className="whitespace-pre-wrap rounded-md bg-surface p-3 font-sans text-xs leading-relaxed text-muted-foreground">{result.decision.explanation}</pre>
                  {analysis.data?.prediction_id && <Link className="text-xs text-primary hover:underline" href={`/predictions/${analysis.data.prediction_id}`}>Full prediction details →</Link>}
                </>
              )}
            </CardContent>
          </Card>
          {result && (
            <>
              {result.mtf?.available && (
                <SectionCard title="Multi-timeframe">
                  <ul className="space-y-1.5 text-sm">
                    {result.mtf.views.map((v) => (
                      <li key={v.role} className="flex items-center justify-between gap-2">
                        <span>{v.timeframe} <span className="text-xs text-muted-foreground">({v.role})</span></span>
                        <Badge variant={v.direction > 0 ? "buy" : v.direction < 0 ? "sell" : "neutral"}>{v.direction > 0 ? "bullish" : v.direction < 0 ? "bearish" : "neutral"}</Badge>
                      </li>
                    ))}
                  </ul>
                  {result.mtf.conflict && <p className="mt-2 text-xs text-warn">Higher and entry timeframes disagree.</p>}
                </SectionCard>
              )}
              <SectionCard title="Supporting evidence"><EvidenceList evidence={result.decision.evidence} /></SectionCard>
            </>
          )}
          <AnalysisOnlyNotice />
        </aside>
      </div>
    </>
  );
}

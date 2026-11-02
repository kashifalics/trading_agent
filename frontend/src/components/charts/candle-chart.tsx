"use client";

import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPrimitivePaneRenderer,
  type IPrimitivePaneView,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Candle } from "@/lib/types";
import type { ChartLine, ChartMarker, ChartSegment, ChartZone } from "./overlays";

type DrawTarget = Parameters<IPrimitivePaneRenderer["draw"]>[0];

/** Draws the analysis layers behind the candles: bordered zones (origin bar to the right edge, one label chip each) and level segments. */
class ZonesPrimitive implements ISeriesPrimitive<Time> {
  zones: ChartZone[] = [];
  segments: ChartSegment[] = [];
  private param?: SeriesAttachedParameter<Time>;
  private view: IPrimitivePaneView = {
    zOrder: () => "bottom",
    renderer: () => ({
      draw: (target: DrawTarget) => {
        const p = this.param;
        if (!p) return;
        target.useBitmapCoordinateSpace((scope) => {
          const ctx = scope.context;
          const hr = scope.horizontalPixelRatio, vr = scope.verticalPixelRatio;
          const ts = p.chart.timeScale();
          const chip = (text: string, x: number, y: number, color: string, align: "left" | "right" = "left") => {
            ctx.font = `600 ${10 * vr}px Poppins, system-ui, sans-serif`;
            const w = ctx.measureText(text).width + 8 * hr, h = 14 * vr;
            const x0 = align === "right" ? x - w : x;
            ctx.fillStyle = "rgba(255,255,255,0.92)";
            ctx.strokeStyle = color;
            ctx.lineWidth = 1 * hr;
            ctx.beginPath();
            ctx.roundRect(x0, y - h / 2, w, h, 4 * hr);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = color;
            ctx.textBaseline = "middle";
            ctx.fillText(text, x0 + 4 * hr, y + 0.5 * vr);
            return w;
          };
          let chipRight = scope.bitmapSize.width - 6 * hr; // zone chips stack leftwards from the right edge so they never overlap
          for (const z of this.zones) {
            const x1 = ts.timeToCoordinate(z.from as UTCTimestamp);
            const y1 = p.series.priceToCoordinate(z.high);
            const y2 = p.series.priceToCoordinate(z.low);
            if (y1 === null || y2 === null) continue;
            const left = Math.max(0, (x1 ?? 0) * hr);
            const top = Math.min(y1, y2) * vr;
            const h = Math.max(1, Math.abs(y2 - y1) * vr);
            ctx.fillStyle = z.color;
            ctx.fillRect(left, top, scope.bitmapSize.width - left, h);
            if (z.border) {
              ctx.strokeStyle = z.border;
              ctx.lineWidth = 1 * hr;
              ctx.strokeRect(left, top, scope.bitmapSize.width - left, h);
            }
            chipRight -= chip(z.label, chipRight, top + h / 2, z.border ?? "rgba(20,32,107,0.7)", "right") + 4 * hr;
          }
          for (const g of this.segments) {
            const x1 = ts.timeToCoordinate(g.from as UTCTimestamp);
            const x2 = ts.timeToCoordinate(g.to as UTCTimestamp);
            const y = p.series.priceToCoordinate(g.price);
            if (x2 === null || y === null) continue;
            const xa = Math.max(0, (x1 ?? 0) * hr), xb = x2 * hr, yy = y * vr;
            ctx.strokeStyle = g.color;
            ctx.lineWidth = 1.4 * hr;
            ctx.setLineDash(g.dashed ? [5 * hr, 4 * hr] : []);
            ctx.beginPath();
            ctx.moveTo(xa, yy);
            ctx.lineTo(xb, yy);
            ctx.stroke();
            ctx.setLineDash([]);
            chip(g.label, xb + 3 * hr, yy + (g.above ? -10 : 10) * vr, g.color);
          }
        });
      },
    }),
  };
  attached(param: SeriesAttachedParameter<Time>) {
    this.param = param;
  }
  detached() {
    this.param = undefined;
  }
  paneViews() {
    return [this.view];
  }
  setLayers(z: ChartZone[], g: ChartSegment[]) {
    this.zones = z;
    this.segments = g;
    this.param?.requestUpdate();
  }
}

export interface CandleChartProps {
  candles: Candle[];
  precision: number;
  markers?: ChartMarker[];
  zones?: ChartZone[];
  segments?: ChartSegment[];
  lines?: ChartLine[];
  height?: number;
  resetKey?: string; // re-fit the view when this changes (symbol/timeframe)
}

export function CandleChart({ candles, precision, markers = [], zones = [], segments = [], lines = [], height = 520, resetKey }: CandleChartProps) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const mk = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const zp = useRef<ZonesPrimitive | null>(null);
  const priceLines = useRef<IPriceLine[]>([]);

  useEffect(() => {
    if (!el.current) return;
    const c = createChart(el.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#6f7d93", fontSize: 11, fontFamily: "Poppins, system-ui, sans-serif" },
      grid: { vertLines: { color: "rgba(33,72,140,0.05)" }, horzLines: { color: "rgba(33,72,140,0.06)" } },
      rightPriceScale: { borderColor: "#e5ecf5" },
      timeScale: { borderColor: "#e5ecf5", timeVisible: true, secondsVisible: false },
      crosshair: { mode: CrosshairMode.Normal },
    });
    const s = c.addSeries(CandlestickSeries, {
      upColor: "#4caf50", downColor: "#ef5350", borderVisible: false, wickUpColor: "#4caf50", wickDownColor: "#ef5350",
    });
    const z = new ZonesPrimitive();
    s.attachPrimitive(z);
    chart.current = c;
    series.current = s;
    zp.current = z;
    mk.current = createSeriesMarkers(s, []);
    return () => {
      c.remove();
      chart.current = series.current = mk.current = zp.current = null;
      priceLines.current = [];
    };
  }, []);

  useEffect(() => {
    series.current?.applyOptions({ priceFormat: { type: "price", precision, minMove: Math.pow(10, -precision) } });
  }, [precision]);

  useEffect(() => {
    series.current?.setData(candles.map((c) => ({ time: c.time as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close })));
  }, [candles]);

  useEffect(() => {
    const n = candles.length;
    const ts = chart.current?.timeScale();
    if (!ts) return;
    if (n > 200) ts.setVisibleLogicalRange({ from: n - 200, to: n + 8 });
    else ts.fitContent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey, candles.length > 0]);

  useEffect(() => {
    mk.current?.setMarkers(markers.map((m) => ({ ...m, time: m.time as UTCTimestamp })));
  }, [markers]);

  useEffect(() => {
    zp.current?.setLayers(zones, segments);
  }, [zones, segments]);

  useEffect(() => {
    const s = series.current;
    if (!s) return;
    priceLines.current.forEach((l) => s.removePriceLine(l));
    priceLines.current = lines.map((l) =>
      s.createPriceLine({ price: l.price, color: l.color, lineWidth: 1, lineStyle: l.dashed ? LineStyle.Dashed : LineStyle.Solid, axisLabelVisible: true, title: l.title }),
    );
  }, [lines]);

  return <div ref={el} style={{ height }} className="w-full overflow-hidden rounded-md border" role="img" aria-label="Candlestick chart" />;
}

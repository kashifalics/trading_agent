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
import type { ChartLine, ChartMarker, ChartZone } from "./overlays";

type DrawTarget = Parameters<IPrimitivePaneRenderer["draw"]>[0];

/** Draws translucent rectangles (FVG / order blocks / supply-demand) from their origin bar to the right edge. */
class ZonesPrimitive implements ISeriesPrimitive<Time> {
  zones: ChartZone[] = [];
  private param?: SeriesAttachedParameter<Time>;
  private view: IPrimitivePaneView = {
    zOrder: () => "bottom",
    renderer: () => ({
      draw: (target: DrawTarget) => {
        const p = this.param;
        if (!p) return;
        target.useBitmapCoordinateSpace((scope) => {
          const ctx = scope.context;
          const ts = p.chart.timeScale();
          for (const z of this.zones) {
            const x1 = ts.timeToCoordinate(z.from as UTCTimestamp);
            const y1 = p.series.priceToCoordinate(z.high);
            const y2 = p.series.priceToCoordinate(z.low);
            if (y1 === null || y2 === null) continue;
            const left = Math.max(0, (x1 ?? 0) * scope.horizontalPixelRatio);
            const top = Math.min(y1, y2) * scope.verticalPixelRatio;
            const h = Math.max(1, Math.abs(y2 - y1) * scope.verticalPixelRatio);
            ctx.fillStyle = z.color;
            ctx.fillRect(left, top, scope.bitmapSize.width - left, h);
            ctx.fillStyle = "rgba(20,32,107,0.7)";
            ctx.font = `${10 * scope.verticalPixelRatio}px sans-serif`;
            ctx.fillText(z.label, left + 4 * scope.horizontalPixelRatio, top + 11 * scope.verticalPixelRatio);
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
  setZones(z: ChartZone[]) {
    this.zones = z;
    this.param?.requestUpdate();
  }
}

export interface CandleChartProps {
  candles: Candle[];
  precision: number;
  markers?: ChartMarker[];
  zones?: ChartZone[];
  lines?: ChartLine[];
  height?: number;
  resetKey?: string; // re-fit the view when this changes (symbol/timeframe)
}

export function CandleChart({ candles, precision, markers = [], zones = [], lines = [], height = 520, resetKey }: CandleChartProps) {
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
    zp.current?.setZones(zones);
  }, [zones]);

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

"use client";

import { AreaSeries, ColorType, LineSeries, createChart, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";

export interface SeriesPoint {
  time: number;
  value: number;
}

export function SeriesChart({
  data,
  color,
  kind = "line",
  height = 220,
  label,
  precision = 2,
}: {
  data: SeriesPoint[];
  color: string;
  kind?: "line" | "area";
  height?: number;
  label: string;
  precision?: number;
}) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!el.current || !data.length) return;
    const c = createChart(el.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#0a0e17" }, textColor: "#8a94a6", fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: "rgba(138,148,166,0.07)" } },
      rightPriceScale: { borderColor: "#1d2433" },
      timeScale: { borderColor: "#1d2433", timeVisible: true },
    });
    const fmt = { type: "price" as const, precision, minMove: Math.pow(10, -precision) };
    const s =
      kind === "area"
        ? c.addSeries(AreaSeries, { lineColor: color, topColor: `${color}55`, bottomColor: `${color}08`, lineWidth: 2, priceFormat: fmt })
        : c.addSeries(LineSeries, { color, lineWidth: 2, priceFormat: fmt });
    s.setData(data.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
    c.timeScale().fitContent();
    return () => c.remove();
  }, [data, color, kind, precision]);
  return <div ref={el} style={{ height }} className="w-full overflow-hidden rounded-md border" role="img" aria-label={label} />;
}

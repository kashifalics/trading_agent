import type { ChartDetail } from "@/lib/store";
import { COLORS } from "./overlays";

/** Key to the drawings so every mark can be read. Counts show what is drawn, so a sparse chart is never mistaken for a missing analysis. */
export function ChartLegend({ detail, counts }: { detail: ChartDetail; counts: { zones: number; structure: number; markers: number } }) {
  const item = (swatch: React.ReactNode, text: string) => (
    <span className="inline-flex items-center gap-1.5">{swatch}{text}</span>
  );
  return (
    <div data-testid="chart-legend" className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {item(<span className="h-3 w-5 rounded-sm border" style={{ background: "rgba(76,175,80,0.16)", borderColor: "rgba(76,175,80,0.55)" }} />, `Zone (FVG / OB / supply-demand, unmitigated): ${counts.zones}`)}
      {item(<span className="w-5 border-t-2" style={{ borderColor: COLORS.bear }} />, `Broken level (BOS dashed, CHoCH solid): ${counts.structure}`)}
      {item(<span style={{ color: COLORS.bull }}>▲</span>, "Candle pattern")}
      {item(<span style={{ color: COLORS.warn }}>●</span>, "Liquidity sweep")}
      <span className="ml-auto">{detail === "clean" ? "Clean: nearest zones and latest events only. Switch to Detailed for the fuller history." : "Detailed: fuller history, expect more overlap."}</span>
    </div>
  );
}

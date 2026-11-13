"use client";

// Overview building blocks: KPI tiles with sparklines, an area chart and a donut, drawn as plain SVG from backend data only.

import type { LucideIcon } from "lucide-react";
import { useId } from "react";
import { cn } from "@/lib/utils";

const TONES = {
  violet: "bg-[hsl(252_72%_60%)] text-white",
  green: "bg-[hsl(146_55%_38%)] text-white",
  blue: "bg-[hsl(222_70%_52%)] text-white",
  orange: "bg-[hsl(28_85%_50%)] text-white",
} as const;
export type Tone = keyof typeof TONES;
const STROKE: Record<Tone, string> = { violet: "#8b6cff", green: "#34d07f", blue: "#6b8cff", orange: "#f6a03e" };

/** A small line of the last values (no axes): the shape of a real series, never decoration. */
export function Sparkline({ values, tone = "violet", className, label }: { values: number[]; tone?: Tone; className?: string; label: string }) {
  const id = useId();
  if (values.length < 2) return null;
  const W = 120, H = 32;
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * W, H - 2 - ((v - lo) / span) * (H - 4)]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={cn("h-8 w-full", className)} role="img" aria-label={label} preserveAspectRatio="none">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={STROKE[tone]} stopOpacity="0.35" />
          <stop offset="100%" stopColor={STROKE[tone]} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${d} L${W},${H} L0,${H} Z`} fill={`url(#${id})`} />
      <path d={d} fill="none" stroke={STROKE[tone]} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function KpiTile({ icon: Icon, tone, label, value, sub, delta, spark, testId }: {
  icon: LucideIcon; tone: Tone; label: string; value: React.ReactNode; sub?: React.ReactNode; delta?: number | null;
  spark?: number[]; testId?: string;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-border/70 bg-card p-4 shadow-card" data-testid={testId}>
      <div className="flex items-center gap-2.5">
        <span className={cn("flex h-8 w-8 items-center justify-center rounded-lg", TONES[tone])}><Icon className="h-4 w-4" aria-hidden /></span>
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
      </div>
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="num truncate text-2xl font-bold tracking-tight">{value}</div>
          <div className="text-xs text-muted-foreground">
            {delta != null && <span className={cn("num mr-1 font-semibold", delta >= 0 ? "text-bull" : "text-bear")}>{delta >= 0 ? "+" : ""}{delta.toFixed(2)}%</span>}
            {sub}
          </div>
        </div>
        {spark && spark.length > 1 && <div className="w-28 shrink-0"><Sparkline values={spark} tone={tone} label={`${label} trend`} /></div>}
      </div>
    </div>
  );
}

/** Area chart of one series with a violet gradient, min / max / last labels; values and their unit come from the caller. */
export function AreaChart({ values, label, unit = "", height = 220 }: { values: { t: string; v: number }[]; label: string; unit?: string; height?: number }) {
  const id = useId();
  if (values.length < 2) return <p className="p-6 text-sm text-muted-foreground">Not enough data for a chart yet.</p>;
  const W = 700, H = height, P = { l: 56, r: 12, t: 12, b: 24 };
  const vs = values.map((x) => x.v);
  const lo = Math.min(0, ...vs), hi = Math.max(0, ...vs), span = hi - lo || 1;
  const x = (i: number) => P.l + (i / (values.length - 1)) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - (v - lo) / span) * (H - P.t - P.b);
  const d = values.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const ticks = [hi, (hi + lo) / 2, lo];
  const fmt = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(Math.abs(span) < 10 ? 2 : 1)}${unit}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${label}: ${values.length} points, now ${fmt(vs[vs.length - 1])}`}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8b6cff" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#8b6cff" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {ticks.map((v, k) => (
        <g key={k}>
          <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} stroke="rgba(255,255,255,0.06)" />
          <text x={P.l - 8} y={y(v) + 4} textAnchor="end" className="fill-muted-foreground text-[11px]">{fmt(v)}</text>
        </g>
      ))}
      {lo < 0 && hi > 0 && <line x1={P.l} x2={W - P.r} y1={y(0)} y2={y(0)} stroke="rgba(255,255,255,0.18)" strokeDasharray="3 4" />}
      <path d={`${d} L${x(values.length - 1)},${y(lo)} L${x(0)},${y(lo)} Z`} fill={`url(#${id})`} />
      <path d={d} fill="none" stroke="#a48cff" strokeWidth={2} strokeLinejoin="round" />
      <text x={P.l} y={H - 6} className="fill-muted-foreground text-[11px]">{values[0].t.slice(0, 10)}</text>
      <text x={W - P.r} y={H - 6} textAnchor="end" className="fill-muted-foreground text-[11px]">{values[values.length - 1].t.slice(0, 10)}</text>
    </svg>
  );
}

export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

export function Donut({ segments, center, sub, label }: { segments: DonutSegment[]; center: string; sub?: string; label: string }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const R = 52, C = 2 * Math.PI * R;
  let acc = 0;
  return (
    <div className="flex flex-wrap items-center gap-5">
      <svg viewBox="0 0 140 140" className="h-36 w-36 shrink-0" role="img" aria-label={`${label}: ${segments.map((s) => `${s.label} ${s.value}`).join(", ")}`}>
        <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="18" />
        {total > 0 && segments.filter((s) => s.value > 0).map((s) => {
          const len = (s.value / total) * C;
          const el = (
            <circle key={s.label} cx="70" cy="70" r={R} fill="none" stroke={s.color} strokeWidth="18" strokeDasharray={`${len} ${C - len}`}
              strokeDashoffset={-acc} transform="rotate(-90 70 70)" />
          );
          acc += len;
          return el;
        })}
        <text x="70" y="70" textAnchor="middle" className="fill-foreground text-[22px] font-bold">{center}</text>
        {sub && <text x="70" y="88" textAnchor="middle" className="fill-muted-foreground text-[10px]">{sub}</text>}
      </svg>
      <ul className="min-w-0 flex-1 space-y-2 text-sm">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />{s.label}</span>
            <span className="num text-muted-foreground">{s.value} {total > 0 ? `(${Math.round((s.value / total) * 100)}%)` : ""}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

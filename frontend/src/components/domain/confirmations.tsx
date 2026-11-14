"use client";

// The confirmation matrix of a signal (docs/engine_v2/CONFIRMATION_DESIGN.md section 9): a row of chips on the card and the full
// evidence on demand. Negative evidence is never hidden; evidence categories say whether they are tested, failed or a gate.

import type { Confirmation, Verdict, VolumeInfo, VsaInfo } from "@/lib/engine-types";
import { cn } from "@/lib/utils";

const CHIPS: [string, string][] = [["trend", "Trend"], ["structure", "Structure"], ["vsa", "VSA"], ["momentum", "Momentum"],
  ["volatility", "Volatility"], ["execution", "Spread"], ["rr", "R:R"]];

const TONE: Record<Verdict, string> = {
  PASS: "border-bull/40 bg-bull/10 text-bull",
  FAIL: "border-bear/40 bg-bear/10 text-bear",
  NEUTRAL: "border-border bg-muted/40 text-muted-foreground",
  UNAVAILABLE: "border-dashed border-border text-muted-foreground",
};

const VSA_STATE: Record<Verdict, string> = { PASS: "VSA confirming", NEUTRAL: "VSA neutral", FAIL: "VSA contradictory", UNAVAILABLE: "VSA unavailable" };

/** Seven chips: Trend, Structure, VSA, Momentum, Volatility, Spread, R:R. Nothing at all when the result carries no matrix. */
export function ConfirmationChips({ items }: { items?: Confirmation[] }) {
  if (!items || items.length === 0) return null;
  const by = new Map(items.map((c) => [c.key, c]));
  return (
    <div className="flex flex-wrap gap-1.5" data-testid="confirmation-chips" aria-label="Confirmations">
      {CHIPS.map(([key, label]) => {
        const c = by.get(key);
        if (!c) return null;
        return (
          <span key={key} data-testid={`chip-${key}`} {...(c.mandatory ? {} : { "data-note": c.note })}
            title={`${c.label}: ${c.reason}${c.mandatory ? "" : ` (${c.note})`}`}
            className={cn("inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold", TONE[c.verdict],
              c.gating && "ring-1 ring-primary/60")}>
            {label} <span className="num">{c.verdict}</span>
            {!c.mandatory && !c.gating && <span className="font-normal opacity-70" aria-hidden>·</span>}
          </span>
        );
      })}
    </div>
  );
}

function volumeNote(v: VolumeInfo): string {
  if (v.type === "tick") return "price updates at one broker, not market-wide traded volume";
  if (v.type === "base") return "coins traded on one exchange, not the whole market";
  if (v.type === "venue") return "liquidity at one venue, research only";
  return "no volume from this source";
}

function fmtEvidence(x: unknown): string {
  if (x === null || x === undefined) return "—";
  if (typeof x === "number") return Number.isInteger(x) ? String(x) : x.toFixed(Math.abs(x) < 1 ? 4 : 2);
  if (typeof x === "string") return x;
  return "";
}

/** Every component's verdict and reason, the indicator values, the volume type and the VSA events with their state. */
export function ConfirmationDetail({ items, volume, vsa }: { items?: Confirmation[]; volume?: VolumeInfo | null; vsa?: VsaInfo | null }) {
  if (!items || items.length === 0) return null;
  const vsaComp = items.find((c) => c.key === "vsa");
  const vsaText = vsaComp
    ? vsaComp.verdict === "UNAVAILABLE"
      ? (vsaComp.reason.startsWith("VSA unavailable") ? vsaComp.reason : `VSA unavailable: ${vsaComp.reason}`)
      : `${VSA_STATE[vsaComp.verdict]}: ${vsaComp.reason}`
    : null;
  return (
    <div className="space-y-3 rounded-lg border bg-surface/40 p-3 text-xs" data-testid="confirmation-detail">
      <ul className="space-y-1">
        {items.map((c) => (
          <li key={c.key} data-testid={`conf-${c.key}`} className="flex flex-wrap items-baseline gap-x-2">
            <span className={cn("rounded border px-1.5 text-[10px] font-semibold", TONE[c.verdict])}>{c.verdict}</span>
            <span className="font-medium">{c.label}</span>
            <span className="text-muted-foreground">{c.reason}</span>
            {!c.mandatory && <span className="text-[10px] italic text-muted-foreground">({c.note})</span>}
            {!c.mandatory && Object.keys(c.evidence).filter((k) => typeof c.evidence[k] !== "object" || c.evidence[k] === null).length > 0 && (
              <span className="num w-full pl-1 text-[10px] text-muted-foreground">
                {Object.entries(c.evidence).filter(([, v]) => typeof v !== "object" || v === null)
                  .map(([k, v]) => `${k.replace(/_/g, " ")} ${fmtEvidence(v)}`).join(" · ")}
              </span>
            )}
          </li>
        ))}
      </ul>
      {volume && (
        <p data-testid="volume-label">
          <span className="font-medium">Volume:</span> {volume.label} — {volumeNote(volume)}
          {!volume.reliable && volume.type !== "none" && <span className="text-muted-foreground"> (unreliable: {volume.reason})</span>}
        </p>
      )}
      {vsaText && <p data-testid="vsa-state" className="font-medium">{vsaText}</p>}
      {vsa && vsa.events.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4" data-testid="vsa-events">
          {vsa.events.map((e, i) => <li key={i}>{e.text} <span className="text-muted-foreground">({e.state})</span></li>)}
        </ul>
      )}
      {vsa && (
        <p className="text-muted-foreground" data-testid="vsa-pressure">
          Pressure: {vsa.pressure.side} ({vsa.pressure.source}, {vsa.pressure.value.toFixed(2)})
          {vsa.context ? ` · ${vsa.context}` : ""}
        </p>
      )}
      <p className="text-[10px] text-muted-foreground">
        Evidence categories (VSA, momentum, trend, volatility) change a decision only after Experiment 6 promotes them. No win probability is shown.
      </p>
    </div>
  );
}

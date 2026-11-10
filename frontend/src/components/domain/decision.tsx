"use client";

import { AlertTriangle, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, Stat } from "@/components/ui/card";
import { Meter } from "@/components/ui/misc";
import type { ConfidencePanel, EvidenceItem, Freq, TradePlan } from "@/lib/types";
import { fmtNum, fmtPct, fmtPrice, signClass } from "@/lib/utils";
import { DecisionBadge } from "./common";

export function PlanCard({ decision, plan, precision = 2, waitReasons }: { decision: "BUY" | "SELL" | "WAIT"; plan: TradePlan | null; precision?: number; waitReasons: string[] }) {
  if (decision === "WAIT" || !plan) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <DecisionBadge decision="WAIT" />
          <span className="text-sm text-muted-foreground">No trade is justified right now.</span>
        </div>
        {waitReasons.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {waitReasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <DecisionBadge decision={decision} className="text-sm" />
        <span className="text-xs text-muted-foreground">targets: {plan.target_basis.replace(/_/g, " ")}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat wrap className="col-span-2 sm:col-span-3" label="Entry zone" value={`${fmtPrice(plan.entry_low, precision)} – ${fmtPrice(plan.entry_high, precision)}`} />
        <Stat label="Stop loss" value={<span className="text-bear">{fmtPrice(plan.stop_loss, precision)}</span>} />
        <Stat label="Invalidation" value={fmtPrice(plan.invalidation, precision)} />
        {plan.targets.map((t, i) => (
          <Stat key={t} label={`Target ${i + 1}`} value={<span className="text-bull">{fmtPrice(t, precision)}</span>} />
        ))}
        <Stat label="Risk / reward" value={`1 : ${fmtNum(plan.risk_reward, 2)}`} />
      </div>
    </div>
  );
}

export function EvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  if (!evidence.length) return <p className="text-sm text-muted-foreground">No evidence was computed (insufficient data).</p>;
  return (
    <ul className="divide-y divide-border/60">
      {evidence.map((e) => (
        <li key={e.name} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 py-2.5">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{e.name.replace(/_/g, " ")}</span>
              <Badge>{e.category.replace(/_/g, " ")}</Badge>
              {e.weight === 0 && <Badge variant="wait">weight 0</Badge>}
            </div>
            {e.detail && <p className="mt-0.5 text-xs text-muted-foreground">{e.detail}</p>}
          </div>
          <div className="w-28 text-right">
            <div className={`num text-sm ${signClass(e.score)}`}>{e.score > 0 ? "+" : ""}{fmtNum(e.score, 2)}</div>
            <div className="text-[10px] text-muted-foreground">weight {fmtNum(e.weight, 2)}</div>
          </div>
          <div className="col-span-2">
            <Meter value={e.score} signed />
          </div>
        </li>
      ))}
    </ul>
  );
}

function FreqRow({ label, f, base }: { label: string; f: Freq; base: Freq }) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-baseline gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="num">
        {fmtPct(f.frequency)} <span className="text-xs text-muted-foreground">({fmtPct(f.ci_low)}–{fmtPct(f.ci_high)} · n={f.n})</span>
        <span className="ml-2 text-xs text-muted-foreground">base {fmtPct(base.frequency)}</span>
      </span>
    </div>
  );
}

function Section({ title, tag, children }: { title: string; tag?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2 rounded-md border bg-surface/60 p-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h4>
        {tag && <Badge>{tag}</Badge>}
      </div>
      {children}
    </div>
  );
}

/** Five deliberately separate notions of certainty; none is blended into a single "confidence %". */
export function ConfidencePanelView({ panel }: { panel: ConfidencePanel }) {
  const mp = panel.model_probability;
  const ro = panel.research_only_model_output;
  const hf = panel.historical_frequency;
  const score = panel.analytical_confluence.score;
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="confidence-panel">
      <Section title="Model probability" tag="calibrated + validated only">
        {mp ? (
          <div className="grid grid-cols-3 gap-2">
            <Stat label="Long TP first" value={fmtPct(mp.p_long_tp_first, 1)} />
            <Stat label="Short TP first" value={fmtPct(mp.p_short_tp_first, 1)} />
            <Stat label="Neither" value={fmtPct(mp.p_neither, 1)} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No validated, calibrated model — no probability is shown.</p>
        )}
        {ro && (
          <div className="rounded border border-warn/30 bg-warn/5 p-2 text-xs text-muted-foreground">
            <Badge variant="wait">research only</Badge> long {fmtPct(ro.p_long_tp_first)} · short {fmtPct(ro.p_short_tp_first)} · neither {fmtPct(ro.p_neither)}.{" "}
            {ro.note}
          </div>
        )}
      </Section>

      <Section title="Historical frequency" tag="not a probability">
        {hf ? (
          <div className="space-y-1.5">
            <FreqRow label="Long: TP before SL" f={hf.long_tp_before_sl} base={hf.base_rate_long} />
            <FreqRow label="Short: TP before SL" f={hf.short_tp_before_sl} base={hf.base_rate_short} />
            <p className="text-xs text-muted-foreground">
              {hf.n_obs} similar historical situations{hf.sufficient ? "" : " (too few to rely on)"}. {hf.label}.
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Not enough history for analogue statistics.</p>
        )}
      </Section>

      <Section title="Analytical confluence" tag="agreement of evidence">
        <div className="flex items-baseline gap-2">
          <span className={`num text-2xl ${signClass(score)}`}>{score === null ? "—" : `${score > 0 ? "+" : ""}${fmtNum(score, 2)}`}</span>
          <span className="text-xs text-muted-foreground">{panel.analytical_confluence.scale}</span>
        </div>
        <Meter value={score ?? 0} signed />
        <p className="text-xs text-muted-foreground">Rule agreement, not a likelihood of profit.</p>
      </Section>

      <Section title="Data quality" tag="inputs">
        <div className="flex items-baseline gap-2">
          <span className="num text-2xl">{fmtNum(panel.data_quality.score, 2)}</span>
          <span className="text-xs text-muted-foreground">/ 1.00</span>
        </div>
        <Meter value={panel.data_quality.score} />
        {panel.data_quality.issues.length > 0 && (
          <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
            {panel.data_quality.issues.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
        )}
      </Section>

      {panel.uncertainty.length > 0 && (
        <div className="md:col-span-2">
          <Section title="Uncertainty & caveats">
            <ul className="space-y-1 text-xs text-muted-foreground">
              {panel.uncertainty.map((u) => (
                <li key={u} className="flex gap-2">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" aria-hidden /> {u}
                </li>
              ))}
            </ul>
          </Section>
        </div>
      )}
    </div>
  );
}

export function AnalysisOnlyNotice() {
  return (
    <div className="flex items-start gap-2 rounded-md border bg-surface/60 p-3 text-xs text-muted-foreground">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
      Analysis only — nothing is executed and no account is connected. Past patterns do not guarantee future results.
    </div>
  );
}

export function SectionCard({ title, actions, children }: { title: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {actions}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

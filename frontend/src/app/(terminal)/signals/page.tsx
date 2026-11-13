"use client";

import { Info } from "lucide-react";
import Link from "next/link";
import { EmptyState, PageHeader, QueryState } from "@/components/domain/common";
import { CategoryLegend, SignalCard, SignalHistory } from "@/components/domain/engine";
import { Checkbox } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { useEngineSummary } from "@/lib/hooks";
import { useSettings } from "@/lib/store";
import { timeAgo } from "@/lib/utils";

export default function SignalsPage() {
  const q = useEngineSummary();
  const { experimentalMode, set } = useSettings();
  return (
    <>
      <PageHeader
        title="Signals"
        description="One clear action per instrument: BUY, SELL, WAIT FOR BUY, WAIT FOR SELL, EXIT or NO TRADE, with the entry, stop-loss and three targets. The best opportunity is first. Analysis only: no orders are placed."
        actions={
          <>
            <Checkbox label="Show hypothetical trade plans (unvalidated)" checked={experimentalMode}
              onChange={(e) => set({ experimentalMode: e.target.checked })} />
            <Link href="/signals/classic" className="text-xs font-medium text-primary hover:underline">Engine v1 checklist</Link>
          </>
        }
      />
      <p role="note" className="mb-4 flex items-start gap-2 rounded-md border border-warn/30 bg-warn/5 p-3 text-sm text-warn" data-testid="signals-note">
        <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <span>
          <strong>BUY / SELL</strong>: a strategy&apos;s entry conditions are met now. <strong>WAIT FOR BUY / SELL</strong>: a valid setup waiting
          for its exact entry price. <strong>No strategy has passed research validation yet</strong>, so every plan is an{" "}
          <strong>UNVALIDATED — HYPOTHETICAL TRADE PLAN</strong> with no proven edge and no win probability. High-impact news is not filtered.
        </span>
      </p>
      <CategoryLegend />
      <QueryState query={q} skeleton={<div className="grid grid-cols-1 gap-4 xl:grid-cols-2">{[0, 1, 2, 3].map((k) => <Skeleton key={k} className="h-72" />)}</div>}
        isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="No instruments configured" hint="Set SIGNAL_SYMBOLS in the backend .env." />}>
        {(d) => (
          <div className="space-y-5">
            <p className="text-xs text-muted-foreground" data-testid="engine-updated">
              Updated {timeAgo(d.generated_at)} · refreshes automatically · engine {d.engine_version}
            </p>
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2" data-testid="signal-cards">
              {d.items.map((i) => <SignalCard key={i.symbol} item={i} />)}
            </div>
            <SignalHistory precisions={Object.fromEntries(d.items.map((i) => [i.symbol, i.price_precision ?? 2]))} />
            <p className="text-xs text-muted-foreground">{d.research_note} {d.news.note}</p>
          </div>
        )}
      </QueryState>
    </>
  );
}

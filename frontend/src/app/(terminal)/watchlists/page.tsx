"use client";

import { Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import { DecisionBadge, EmptyState, ErrorState, InstrumentSelect, PageHeader, QueryState } from "@/components/domain/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/form";
import { useInstruments, usePredictions, useQuotes, useWatchlistMutations, useWatchlists } from "@/lib/hooks";
import { fmtPrice, timeAgo } from "@/lib/utils";

export default function WatchlistsPage() {
  const lists = useWatchlists();
  const quotes = useQuotes();
  const preds = usePredictions({ limit: 100 });
  const instruments = useInstruments();
  const m = useWatchlistMutations();
  const [name, setName] = useState("");
  const [pick, setPick] = useState("XAUUSD");

  return (
    <>
      <PageHeader title="Watchlists" description="Group instruments you follow. Quotes and the latest stored decision are shown per item." />
      <form
        className="mb-4 flex max-w-lg gap-2"
        onSubmit={(e) => { e.preventDefault(); if (name.trim()) m.create.mutate(name.trim(), { onSuccess: () => setName("") }); }}
      >
        <Input aria-label="Watchlist name" placeholder="New watchlist name" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
        <Button type="submit" loading={m.create.isPending}><Plus className="h-4 w-4" /> Create</Button>
      </form>
      {m.create.isError && <ErrorState error={m.create.error} />}
      <QueryState query={lists} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No watchlists yet" hint="Create one above, then add instruments." />}>
        {(d) => (
          <div className="grid gap-4 lg:grid-cols-2">
            {d.map((w) => (
              <Card key={w.id}>
                <CardHeader>
                  <CardTitle>{w.name}</CardTitle>
                  <Button size="icon" variant="ghost" aria-label={`Delete ${w.name}`} onClick={() => m.remove.mutate(w.id)}><Trash2 className="h-4 w-4" /></Button>
                </CardHeader>
                <CardContent className="space-y-3">
                  {w.items.length === 0 && <p className="text-sm text-muted-foreground">Empty.</p>}
                  {w.items.map((it) => {
                    const q = quotes.data?.find((x) => x.symbol === it.symbol);
                    const p = preds.data?.items.find((x) => x.symbol === it.symbol);
                    const prec = instruments.data?.find((i) => i.canonical_symbol === it.symbol)?.price_precision ?? 2;
                    return (
                      <div key={it.id} className="flex items-center justify-between gap-2 text-sm">
                        <span className="font-medium">{it.symbol}</span>
                        <span className="num text-muted-foreground">{q?.status === "ok" ? fmtPrice(q.price, prec) : q ? "no quote" : "…"}</span>
                        <span className="flex items-center gap-2">
                          {p ? <><DecisionBadge decision={p.decision} /><span className="text-[11px] text-muted-foreground">{p.timeframe} · {timeAgo(p.created_at)}</span></> : <span className="text-xs text-muted-foreground">no analysis</span>}
                          <Button size="icon" variant="ghost" aria-label={`Remove ${it.symbol}`} onClick={() => m.removeItem.mutate({ id: w.id, itemId: it.id })}><X className="h-3.5 w-3.5" /></Button>
                        </span>
                      </div>
                    );
                  })}
                  <div className="flex gap-2 border-t pt-3">
                    <InstrumentSelect value={pick} onChange={setPick} />
                    <Button variant="outline" onClick={() => m.addItem.mutate({ id: w.id, symbol: pick })}>Add</Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </QueryState>
    </>
  );
}

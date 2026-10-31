"use client";

import { ExternalLink, RefreshCw, Search } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, PageHeader, QueryState } from "@/components/domain/common";
import { SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useCoverage, useProbe, useProviders, useSync } from "@/lib/hooks";
import { fmtDate, timeAgo } from "@/lib/utils";

const STATUS_VARIANT = { configured: "buy", needs_api_key: "wait", no_adapter: "neutral" } as const;

export default function DataSourcesPage() {
  const providers = useProviders();
  const coverage = useCoverage();
  const sync = useSync();
  const probe = useProbe();
  const [open, setOpen] = useState<string | null>(null);
  const [probeOut, setProbeOut] = useState<Record<string, unknown> | null>(null);

  return (
    <>
      <PageHeader title="Data Sources" description="Provider status, what each instrument is mapped to, stored history and gaps. Different providers' candles are never mixed as if identical." />
      <QueryState query={providers}>
        {(list) => (
          <div className="grid gap-4 lg:grid-cols-3">
            {list.map((p) => (
              <Card key={p.code}>
                <CardHeader>
                  <CardTitle>{p.name}</CardTitle>
                  <Badge variant={STATUS_VARIANT[p.status]}>{p.status.replace(/_/g, " ")}</Badge>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  {p.free_plan && (
                    <dl className="space-y-1 text-xs">
                      {Object.entries(p.free_plan).filter(([k]) => ["price", "auth", "rate_limit", "history", "caveat"].includes(k)).map(([k, v]) => (
                        <div key={k}><dt className="inline font-medium capitalize">{k.replace(/_/g, " ")}: </dt><dd className="inline text-muted-foreground">{String(v)}</dd></div>
                      ))}
                    </dl>
                  )}
                  {p.note && <p className="text-xs text-muted-foreground">{p.note}</p>}
                  {p.licensing && <p className="text-[11px] text-muted-foreground">Licensing: {p.licensing}</p>}
                  <p className="text-[11px] text-muted-foreground">API quota: not reported by this adapter — see the provider dashboard.</p>
                  <ul className="space-y-1 border-t pt-2">
                    {p.instruments.map((i) => (
                      <li key={i.symbol} className="flex items-center justify-between gap-2 text-xs">
                        <span>{i.symbol} → <span className="num">{i.provider_symbol}</span> <span className="text-muted-foreground">({i.market_kind})</span></span>
                        <Badge variant={i.status === "active" ? "buy" : i.status === "unverified" ? "wait" : "neutral"}>{i.status}</Badge>
                      </li>
                    ))}
                  </ul>
                  <div className="flex gap-3 text-xs">
                    {p.docs_url && <a className="inline-flex items-center gap-1 text-primary hover:underline" href={p.docs_url} target="_blank" rel="noreferrer noopener">Docs <ExternalLink className="h-3 w-3" /></a>}
                    {p.signup_url && <a className="inline-flex items-center gap-1 text-primary hover:underline" href={p.signup_url} target="_blank" rel="noreferrer noopener">Sign-up / plans <ExternalLink className="h-3 w-3" /></a>}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </QueryState>

      <div className="mt-4">
        <SectionCard
          title="Stored coverage"
          actions={
            <div className="flex gap-2">
              <Button size="sm" variant="outline" loading={sync.isPending} onClick={() => sync.mutate({ symbol: "BTCUSDT", timeframe: "1H", bars: 2000 })}><RefreshCw className="h-3.5 w-3.5" /> Sync BTCUSDT 1H</Button>
              <Button size="sm" variant="outline" loading={probe.isPending} onClick={() => probe.mutate({ symbol: "XAUUSD", timeframe: "1H" }, { onSuccess: setProbeOut })}><Search className="h-3.5 w-3.5" /> Probe XAUUSD</Button>
            </div>
          }
        >
          {sync.isError && <ErrorState error={sync.error} />}
          {probe.isError && <ErrorState error={probe.error} />}
          {probeOut && <pre className="mb-3 overflow-auto rounded bg-surface p-3 text-xs text-muted-foreground">{JSON.stringify(probeOut, null, 2)}</pre>}
          <QueryState query={coverage} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No candles stored yet" hint="Use the sync button, or run an analysis with auto-sync. XAUUSD needs TWELVE_DATA_API_KEY in backend/.env; US30 and USOIL are unsupported until a licensed feed adapter is configured." />}>
            {(d) => (
              <Table>
                <THead><TR><TH>Instrument</TH><TH>Provider</TH><TH>TF</TH><TH className="text-right">Candles</TH><TH>From</TH><TH>To</TH><TH className="text-right">Gaps</TH><TH>Last sync</TH></TR></THead>
                <TBody>
                  {d.map((c) => {
                    const k = `${c.instrument}${c.provider}${c.timeframe}`;
                    return (
                      <>
                        <TR key={k}>
                          <TD className="font-medium">{c.instrument}</TD><TD>{c.provider}</TD><TD>{c.timeframe}</TD>
                          <TD className="num text-right">{c.candle_count}</TD>
                          <TD className="num">{fmtDate(c.first_ts, false)}</TD><TD className="num">{fmtDate(c.last_ts)}</TD>
                          <TD className="text-right">
                            {c.gap_count ? <button className="num text-warn underline" onClick={() => setOpen(open === k ? null : k)}>{c.gap_count}</button> : <span className="num">0</span>}
                          </TD>
                          <TD className="text-xs text-muted-foreground">{c.last_sync_status === "error" ? <span className="text-bear">error: {c.last_error}</span> : `${c.last_sync_status ?? "never"} · ${timeAgo(c.last_sync_at)}`}</TD>
                        </TR>
                        {open === k && (
                          <TR key={`${k}-gaps`}><TD colSpan={8} className="bg-surface text-xs text-muted-foreground">
                            Missing candles (first {c.gaps.length} ranges): {c.gaps.map((g) => `${fmtDate(g.start)} → ${fmtDate(g.end)} (${g.missing})`).join(" · ")}
                          </TD></TR>
                        )}
                      </>
                    );
                  })}
                </TBody>
              </Table>
            )}
          </QueryState>
        </SectionCard>
      </div>
    </>
  );
}

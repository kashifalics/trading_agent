"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { InstrumentSelect, PageHeader, QueryState, TimeframeSelect } from "@/components/domain/common";
import { SectionCard } from "@/components/domain/decision";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/form";
import { API_URL, ApiError, api } from "@/lib/api";
import { useHealth } from "@/lib/hooks";
import { useSettings } from "@/lib/store";
import type { AuthStatus } from "@/lib/types";

type KeyCheck = { state: "idle" | "checking" | "ok" | "rejected" | "error"; text?: string };

export default function SettingsPage() {
  const s = useSettings();
  const health = useHealth();
  const qc = useQueryClient();
  const [key, setKey] = useState(s.apiKey);
  const [check, setCheck] = useState<KeyCheck>({ state: "idle" });

  async function saveAndVerify() {
    s.set({ apiKey: key.trim() });
    setCheck({ state: "checking" });
    try {
      const r = await api.get<AuthStatus>("/auth/status");
      setCheck({ state: "ok", text: r.auth_required ? "Key accepted by the server." : "Saved. This server does not require a key (local development mode)." });
      void qc.invalidateQueries();
    } catch (e) {
      const err = e instanceof ApiError ? e : null;
      setCheck(err?.status === 401
        ? { state: "rejected", text: key.trim() ? "The server rejected this key." : "This server requires a key." }
        : { state: "error", text: err?.message ?? "Could not reach the backend." });
    }
  }

  return (
    <>
      <PageHeader title="Settings" description="Client preferences are stored in this browser only. Provider credentials never live here — they belong in backend/.env." />
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="Connection">
          <div className="space-y-3 text-sm">
            <div><Label>Backend URL (build-time, NEXT_PUBLIC_API_URL)</Label><div className="num rounded border bg-surface px-3 py-2">{API_URL}</div></div>
            <div>
              <Label htmlFor="apikey">Platform API key (X-API-Key) — only if the backend runs with AUTH_REQUIRED=true</Label>
              <div className="flex gap-2">
                <Input id="apikey" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder="ati_…" />
                <Button onClick={() => void saveAndVerify()} loading={check.state === "checking"}>Save &amp; verify</Button>
              </div>
              {check.state !== "idle" && check.state !== "checking" && (
                <p role="status" data-testid="key-check" className={check.state === "ok" ? "mt-1 text-xs text-bull" : "mt-1 text-xs text-bear"}>{check.text}</p>
              )}
              <p className="mt-1 text-[11px] text-muted-foreground">This is a key for THIS platform, not a market-data or broker key. It is kept in localStorage and sent only to the backend above.</p>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Defaults">
          <div className="grid grid-cols-2 gap-3">
            <div><Label htmlFor="d-sym">Instrument</Label><InstrumentSelect id="d-sym" value={s.symbol} onChange={(v) => s.set({ symbol: v })} /></div>
            <div><Label htmlFor="d-tf">Timeframe</Label><TimeframeSelect id="d-tf" value={s.timeframe} onChange={(v) => s.set({ timeframe: v })} /></div>
            <div><Label>Higher TF</Label><TimeframeSelect allowNone label="Default higher timeframe" value={s.mtfHigher} onChange={(v) => s.set({ mtfHigher: v })} /></div>
            <div><Label>Intermediate TF</Label><TimeframeSelect allowNone label="Default intermediate timeframe" value={s.mtfIntermediate} onChange={(v) => s.set({ mtfIntermediate: v })} /></div>
          </div>
        </SectionCard>

        <div className="lg:col-span-2">
          <SectionCard title="Backend capabilities">
            <QueryState query={health}>
              {(h) => (
                <div className="space-y-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={h.status === "ok" ? "buy" : "sell"}>{h.status}</Badge>
                    <Badge variant="info">{h.mode.replace("_", " ")}</Badge>
                    <span className="text-xs text-muted-foreground">v{h.version} · {h.env}</span>
                  </div>
                  <dl className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
                    {Object.entries(h.components).map(([k, v]) => (
                      <div key={k} className="flex justify-between border-b border-border/50 py-1"><dt className="text-muted-foreground">{k.replace(/_/g, " ")}</dt><dd className="num">{String(v)}</dd></div>
                    ))}
                  </dl>
                  <p className="text-xs text-muted-foreground">OCR off ⇒ instrument/timeframe and price axis are not read from screenshots (manual calibration points still work). Twelve Data key off ⇒ XAUUSD has no data.</p>
                </div>
              )}
            </QueryState>
          </SectionCard>
        </div>
      </div>
    </>
  );
}

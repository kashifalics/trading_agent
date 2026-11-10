"use client";

import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { ApiError } from "@/lib/api";
import { useInstruments, useTimeframes } from "@/lib/hooks";
import type { Decision, JobStatus } from "@/lib/types";
import { TIMEFRAME_CODES, cn } from "@/lib/utils";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function DecisionBadge({ decision, className }: { decision: Decision; className?: string }) {
  const variant = decision === "BUY" ? "buy" : decision === "SELL" ? "sell" : "wait";
  return (
    <Badge variant={variant} className={cn("num px-2.5 font-semibold tracking-wider", className)}>
      {decision}
    </Badge>
  );
}

export function JobBadge({ status }: { status: JobStatus | string }) {
  const v = status === "completed" ? "buy" : status === "failed" ? "sell" : "info";
  return <Badge variant={v}>{status}</Badge>;
}

/** "Not validated" label for any BUY/SELL setup: nothing in this product has passed out-of-sample validation. */
export function NotValidatedBadge({ status = "not_validated", note, className }: { status?: "validated" | "not_validated"; note?: string; className?: string }) {
  if (status === "validated") return <Badge variant="buy" className={className} title={note}>Validated</Badge>;
  return (
    <Badge variant="wait" className={className} data-testid="not-validated"
      title={note ?? "No strategy or model in this product has passed out-of-sample validation. Hypothetical setup for analysis, not a proven trade."}>
      Not validated
    </Badge>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  if (e?.status === 401) {
    return (
      <div role="alert" className="flex flex-col items-start gap-2 rounded-md border border-warn/40 bg-cta/10 p-4 text-sm">
        <div className="flex items-center gap-2 font-medium text-warn">
          <AlertTriangle className="h-4 w-4" aria-hidden /> {e.message === "Invalid API key" ? "Invalid API key" : "API key required"}
        </div>
        <p className="text-muted-foreground">
          {e.message === "Invalid API key" ? "The saved platform API key was rejected by the server." : "This server requires a platform API key."}{" "}
          <Link href="/settings" className="font-medium text-primary hover:underline">Enter it in Settings</Link>.
        </p>
      </div>
    );
  }
  return (
    <div role="alert" className="flex flex-col items-start gap-2 rounded-md border border-bear/30 bg-bear/5 p-4 text-sm">
      <div className="flex items-center gap-2 font-medium text-bear">
        <AlertTriangle className="h-4 w-4" aria-hidden />
        {e?.code === "network_error" ? "Backend unreachable" : "Request failed"}
      </div>
      <p className="text-muted-foreground">{e?.message ?? (error as Error)?.message ?? "Unknown error"}</p>
      {e?.requestId && <p className="num text-xs text-muted-foreground">request id: {e.requestId}</p>}
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-md border border-dashed p-8 text-center">
      <Inbox className="h-6 w-6 text-muted-foreground" aria-hidden />
      <div className="text-sm font-medium">{title}</div>
      {hint && <p className="max-w-md text-xs text-muted-foreground">{hint}</p>}
      {action}
    </div>
  );
}

/** Renders loading / error / empty / data consistently for any query. */
export function QueryState<T>({
  query,
  isEmpty,
  empty,
  skeleton,
  children,
}: {
  query: { data: T | undefined; isLoading: boolean; isError: boolean; error: unknown; refetch: () => unknown };
  isEmpty?: (d: T) => boolean;
  empty?: React.ReactNode;
  skeleton?: React.ReactNode;
  children: (d: T) => React.ReactNode;
}) {
  if (query.isLoading) return <>{skeleton ?? <Skeleton className="h-24 w-full" />}</>;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (query.data === undefined) return null;
  if (isEmpty?.(query.data)) return <>{empty}</>;
  return <>{children(query.data)}</>;
}

export function InstrumentSelect({ value, onChange, id, onlySupported = false }: { value: string; onChange: (v: string) => void; id?: string; onlySupported?: boolean }) {
  const { data } = useInstruments();
  const list = (data ?? []).filter((i) => !onlySupported || i.supported);
  const opts = list.length ? list : [{ canonical_symbol: value, supported: true, name: value }];
  return (
    <Select id={id} aria-label="Instrument" value={value} onChange={(e) => onChange(e.target.value)}>
      {opts.map((i) => (
        <option key={i.canonical_symbol} value={i.canonical_symbol}>
          {i.canonical_symbol}
          {"supported" in i && !i.supported ? " (no data source)" : ""}
        </option>
      ))}
    </Select>
  );
}

export function TimeframeSelect({
  value,
  onChange,
  id,
  allowNone = false,
  label = "Timeframe",
}: {
  value: string;
  onChange: (v: string) => void;
  id?: string;
  allowNone?: boolean;
  label?: string;
}) {
  const { data } = useTimeframes();
  const codes = data?.map((t) => t.code) ?? TIMEFRAME_CODES;
  return (
    <Select id={id} aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      {allowNone && <option value="">— none —</option>}
      {codes.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </Select>
  );
}

export function SourceNote({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] leading-snug text-muted-foreground">{children}</p>;
}

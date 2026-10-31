"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded bg-muted", className)} />;
}

/** Horizontal meter. `value` in [0,1] (or [-1,1] when signed). */
export function Meter({ value, signed = false, className }: { value: number; signed?: boolean; className?: string }) {
  const v = Math.max(signed ? -1 : 0, Math.min(1, value));
  const width = signed ? Math.abs(v) * 50 : v * 100;
  const left = signed ? (v >= 0 ? 50 : 50 - width) : 0;
  const color = signed ? (v >= 0 ? "bg-bull" : "bg-bear") : v >= 0.7 ? "bg-bull" : v >= 0.5 ? "bg-warn" : "bg-bear";
  return (
    <div className={cn("relative h-1.5 w-full overflow-hidden rounded bg-muted", className)}>
      {signed && <div className="absolute left-1/2 top-0 h-full w-px bg-border" />}
      <div className={cn("absolute top-0 h-full rounded", color)} style={{ left: `${left}%`, width: `${width}%` }} />
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div role="tablist" className="inline-flex rounded-md border bg-surface p-0.5">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cn("rounded px-3 py-1 text-xs font-medium", value === t.id ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground")}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

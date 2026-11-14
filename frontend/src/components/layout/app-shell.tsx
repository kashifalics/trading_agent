"use client";

import {
  Activity,
  BarChart3,
  Boxes,
  Brain,
  Database,
  Eye,
  FlaskConical,
  KeyRound,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Menu,
  Microscope,
  Radar,
  Crosshair,
  Settings,
  Target,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useHealth } from "@/lib/hooks";
import { useSettings } from "@/lib/store";
import { cn } from "@/lib/utils";

export const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/signals", label: "Signals", icon: Activity },
  { href: "/paper", label: "Paper Trading", icon: Wallet },
  { href: "/active", label: "Active Trades", icon: ListChecks },
  { href: "/opportunities", label: "Trade Opportunities", icon: Crosshair },
  { href: "/chart", label: "Chart Analysis", icon: LineChart },
  { href: "/scanner", label: "Market Scanner", icon: Radar },
  { href: "/predictions", label: "Predictions", icon: Target },
  { href: "/gold-research", label: "Gold Research", icon: Microscope },
  { href: "/patterns", label: "Historical Patterns", icon: Boxes },
  { href: "/backtesting", label: "Backtesting", icon: FlaskConical },
  { href: "/performance", label: "Performance", icon: BarChart3 },
  { href: "/watchlists", label: "Watchlists", icon: Eye },
  { href: "/data-sources", label: "Data Sources", icon: Database },
  { href: "/models", label: "Models", icon: Brain },
  { href: "/settings", label: "Settings", icon: Settings },
];

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5 py-2">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "mx-3 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              active ? "bg-nav font-semibold text-nav-foreground shadow-soft" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Shown on every page when the server needs a platform API key and this browser has none saved. */
function ApiKeyBanner() {
  const { data } = useHealth();
  const apiKey = useSettings((s) => s.apiKey);
  const [hydrated, setHydrated] = useState(false); // never flash the banner before the saved key has been loaded
  useEffect(() => {
    if (useSettings.persist.hasHydrated()) setHydrated(true);
    return useSettings.persist.onFinishHydration(() => setHydrated(true));
  }, []);
  if (!hydrated || !data?.auth_required || apiKey) return null;
  return (
    <div role="alert" data-testid="api-key-banner" className="mb-4 flex flex-wrap items-center gap-2 rounded-md border border-warn/40 bg-warn/10 px-4 py-3 text-sm">
      <KeyRound className="h-4 w-4 text-warn" aria-hidden />
      <span>This server requires a platform API key.</span>
      <Link href="/settings" className="font-medium text-primary hover:underline">Enter it in Settings</Link>
    </div>
  );
}

function BackendStatus() {
  const { data, isError, isLoading } = useHealth();
  const ok = data?.status === "ok";
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" role="status" aria-live="polite">
      <span className={cn("h-2 w-2 rounded-full", isLoading ? "bg-muted-foreground" : ok ? "bg-bull" : "bg-bear")} />
      {isLoading ? "connecting…" : isError ? "backend unreachable" : ok ? "backend online" : "backend degraded"}
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border/60 bg-surface shadow-card lg:flex">
        <div className="flex h-16 items-center gap-2.5 px-6">
          <Activity className="h-6 w-6 text-primary" aria-hidden />
          <span className="text-base font-bold tracking-tight">AI Trading Intel</span>
        </div>
        <div className="flex-1 overflow-y-auto">
          <Nav />
        </div>
        <div className="p-5 text-[11px] leading-snug text-muted-foreground">
          Analysis only. No orders are placed and no broker is connected.
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-foreground/40" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 border-r bg-surface">
            <div className="flex h-14 items-center justify-between border-b px-4">
              <span className="text-sm font-semibold">AI Trading Intel</span>
              <button aria-label="Close menu" onClick={() => setOpen(false)}>
                <X className="h-5 w-5" />
              </button>
            </div>
            <Nav onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between bg-background/80 px-4 backdrop-blur sm:px-6">
          <button className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden text-xs text-muted-foreground sm:block">
            Probabilities are shown only when a model is calibrated and validated. WAIT is a valid answer.
          </div>
          <BackendStatus />
        </header>
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-5 sm:px-6">
          <ApiKeyBanner />
          {children}
        </main>
      </div>
    </div>
  );
}

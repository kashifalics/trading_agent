"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export interface OverlayToggles {
  swings: boolean;
  structure: boolean;
  zones: boolean;
  liquidity: boolean;
  patterns: boolean;
  plan: boolean;
}

export type ChartDetail = "clean" | "detailed";

interface SettingsState {
  chartDetail: ChartDetail;
  apiKey: string;
  symbol: string;
  timeframe: string;
  mtfHigher: string;
  mtfIntermediate: string;
  mtfEntry: string;
  overlays: OverlayToggles;
  /** Signals page: account balance and risk per trade (%) for the position-size calculator; live auto-refresh toggle. */
  accountBalance: number;
  riskPct: number;
  contractSizes: Record<string, number>;
  liveSignals: boolean;
  set: (patch: Partial<Omit<SettingsState, "set" | "setOverlay">>) => void;
  setOverlay: (key: keyof OverlayToggles, value: boolean) => void;
}

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      apiKey: "",
      symbol: "BTCUSDT",
      timeframe: "1H",
      mtfHigher: "1D",
      mtfIntermediate: "4H",
      mtfEntry: "1H",
      chartDetail: "clean",
      overlays: { swings: false, structure: true, zones: true, liquidity: true, patterns: false, plan: true },
      accountBalance: 1000,
      riskPct: 0.5,
      contractSizes: {},
      liveSignals: true,
      set: (patch) => set(patch),
      setOverlay: (key, value) => set((s) => ({ overlays: { ...s.overlays, [key]: value } })),
    }),
    {
      name: "ati-settings",
      storage: createJSONStorage(() => localStorage),
      skipHydration: true, // rehydrated in <Providers/> after mount to avoid SSR mismatch
    },
  ),
);

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
  /** Experimental analysis mode: show the hypothetical trade plans (entry, stop, targets) of unvalidated setups, always marked
   *  UNVALIDATED. On by default since settings version 1 (the owner's requirement: prices visible at once). */
  experimentalMode: boolean;
  set: (patch: Partial<Omit<SettingsState, "set" | "setOverlay">>) => void;
  setOverlay: (key: keyof OverlayToggles, value: boolean) => void;
}

export const SETTINGS_STORAGE_KEY = "ati-settings";

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
      experimentalMode: true,
      set: (patch) => set(patch),
      setOverlay: (key, value) => set((s) => ({ overlays: { ...s.overlays, [key]: value } })),
    }),
    {
      name: SETTINGS_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      skipHydration: true, // rehydrated in <Providers/> after mount to avoid SSR mismatch
      version: 1,
      // v1: experimental analysis mode became the default (hypothetical trade plans shown, clearly marked); older saved settings follow
      migrate: (persisted, version) => {
        const s = (persisted ?? {}) as Partial<SettingsState>;
        return (version < 1 ? { ...s, experimentalMode: true } : s) as SettingsState;
      },
    },
  ),
);

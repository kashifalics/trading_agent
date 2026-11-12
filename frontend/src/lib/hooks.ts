"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api";
import { useSettings } from "@/lib/store";
import type { GoldResearch } from "@/lib/research-types";
import type {
  AnaloguesResponse,
  Analysis,
  Backtest,
  CandlesResponse,
  ChartAnalyzeResult,
  Coverage,
  Health,
  Instrument,
  JobAccepted,
  ModelRow,
  Page,
  PatternDefinitions,
  PatternScan,
  PatternsResponse,
  Prediction,
  PredictionDetail,
  PredictionStats,
  ProviderInfo,
  Quote,
  Timeframe,
  Watchlist,
} from "@/lib/types";

import type { OppSummary, OppValidation, OpportunityDetail, ScanAccepted } from "@/lib/opportunity-types";
import type { PaperAccount, PaperAccountChanges, PaperRunResult, PaperSummary, PaperTradeDetail, PaperTradesPage } from "@/lib/paper-types";
import type { SignalAnalysis, SignalsSummary, SignalSync } from "@/lib/signal-types";

export const retryPolicy = (failureCount: number, error: unknown) =>
  failureCount < 2 && (!(error instanceof ApiError) || error.retryable);

const isActive = (s?: string) => s === "queued" || s === "running";

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => api.get<Health>("/health"), refetchInterval: 30_000 });
export const useInstruments = () => useQuery({ queryKey: ["instruments"], queryFn: () => api.get<Instrument[]>("/market/instruments"), staleTime: 60_000 });
export const useTimeframes = () => useQuery({ queryKey: ["timeframes"], queryFn: () => api.get<Timeframe[]>("/market/timeframes"), staleTime: Infinity });
export const useQuotes = () => useQuery({ queryKey: ["quotes"], queryFn: () => api.get<Quote[]>("/market/quotes"), refetchInterval: 15_000 });
export const useCoverage = (symbol?: string) =>
  useQuery({ queryKey: ["coverage", symbol ?? "all"], queryFn: () => api.get<Coverage[]>("/market/coverage", { symbol }) });
export const useProviders = () => useQuery({ queryKey: ["providers"], queryFn: () => api.get<ProviderInfo[]>("/market/providers") });

export const useCandles = (symbol: string, timeframe: string, limit = 600, enabled = true) =>
  useQuery({
    queryKey: ["candles", symbol, timeframe, limit],
    queryFn: () => api.get<CandlesResponse>("/market/candles", { symbol, timeframe, limit }),
    enabled,
    placeholderData: keepPreviousData,
    retry: retryPolicy,
  });

export const usePatterns = (symbol: string, timeframe: string, enabled = true) =>
  useQuery({
    queryKey: ["patterns", symbol, timeframe],
    queryFn: () => api.get<PatternsResponse>("/patterns", { symbol, timeframe, lookback_bars: 600 }),
    enabled,
    retry: retryPolicy,
  });
export const usePatternScan = (symbol: string, recent = 3) =>
  useQuery({
    queryKey: ["pattern-scan", symbol, recent],
    queryFn: () => api.get<PatternScan>("/patterns/scan", { symbol, recent }),
    retry: retryPolicy,
  });
export const usePatternDefinitions = () =>
  useQuery({ queryKey: ["pattern-defs"], queryFn: () => api.get<PatternDefinitions>("/patterns/definitions"), staleTime: Infinity });

/** The experimental-mode flag sent with every request that returns a trading decision (undefined = off). */
export const useExperimental = () => useSettings((s) => s.experimentalMode);
const expParam = (x: boolean) => (x ? { experimental: true } : {});

export const useAnalysis = (id: number | null) => {
  const x = useExperimental();
  return useQuery({
    queryKey: ["analysis", id, x],
    queryFn: () => api.get<Analysis>(`/analysis/${id}`, expParam(x)),
    enabled: id !== null,
    refetchInterval: (q) => (isActive(q.state.data?.status) ? 1500 : false),
  });
};
export const useAnalogues = (id: number | null) =>
  useQuery({ queryKey: ["analogues", id], queryFn: () => api.get<AnaloguesResponse>(`/analysis/${id}/analogues`), enabled: id !== null });
export const useAnalyses = (limit = 10) =>
  useQuery({ queryKey: ["analyses", limit], queryFn: () => api.get<Page<Analysis>>("/analysis", { limit }), refetchInterval: 20_000 });

export interface PredictionFilters {
  symbol?: string;
  decision?: string;
  outcome?: string;
  limit?: number;
  offset?: number;
}
export const usePredictions = (f: PredictionFilters = {}) => {
  const x = useExperimental();
  return useQuery({
    queryKey: ["predictions", f, x],
    queryFn: () => api.get<Page<Prediction>>("/predictions", { limit: 25, ...f, ...expParam(x) }),
    placeholderData: keepPreviousData,
  });
};
export const usePrediction = (id: number) => {
  const x = useExperimental();
  return useQuery({ queryKey: ["prediction", id, x], queryFn: () => api.get<PredictionDetail>(`/predictions/${id}`, expParam(x)), retry: retryPolicy });
};
export const usePredictionStats = () => useQuery({ queryKey: ["prediction-stats"], queryFn: () => api.get<PredictionStats>("/predictions/stats") });

export const useBacktest = (id: number | null) =>
  useQuery({
    queryKey: ["backtest", id],
    queryFn: () => api.get<Backtest>(`/backtests/${id}`),
    enabled: id !== null,
    refetchInterval: (q) => (isActive(q.state.data?.status) ? 2000 : false),
  });
export const useBacktests = () => useQuery({ queryKey: ["backtests"], queryFn: () => api.get<Page<Backtest>>("/backtests", { limit: 20 }) });
export const useStrategies = () => useQuery({ queryKey: ["strategies"], queryFn: () => api.get<{ id: string; description: string }[]>("/backtests/strategies"), staleTime: Infinity });

export const useModels = () => useQuery({ queryKey: ["models"], queryFn: () => api.get<Page<ModelRow>>("/models"), refetchInterval: 10_000 });
export const useWatchlists = () => useQuery({ queryKey: ["watchlists"], queryFn: () => api.get<Watchlist[]>("/watchlists") });

// ---- mutations ----
export interface AnalysisRequest {
  symbol: string;
  timeframe: string;
  mtf: { higher?: string; intermediate?: string; entry?: string };
  lookback_bars: number;
  auto_sync: boolean;
}

export function useRunAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: AnalysisRequest) => api.post<JobAccepted>("/analysis/run", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analyses"] }),
  });
}

export function useSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: { symbol: string; timeframe: string; bars: number }) => api.post<Record<string, unknown>>("/market/sync", req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["coverage"] });
      qc.invalidateQueries({ queryKey: ["candles"] });
      qc.invalidateQueries({ queryKey: ["patterns"] });
    },
  });
}

export const useProbe = () =>
  useMutation({ mutationFn: (req: { symbol: string; timeframe: string }) => api.post<Record<string, unknown>>("/market/coverage/probe", req) });

export function useRunBacktest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: Record<string, unknown>) => api.post<JobAccepted>("/backtests/run", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backtests"] }),
  });
}

export function useTrainModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: Record<string, unknown>) => api.post<{ status: string; note: string }>("/models/train", req),
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["models"] }), 2000),
  });
}

export function useActivateModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post(`/models/${id}/activate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models"] }),
  });
}

export function useRefreshOutcomes() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ updated: number }>("/predictions/refresh-outcomes"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["predictions"] });
      qc.invalidateQueries({ queryKey: ["prediction-stats"] });
    },
  });
}

export const useUploadChart = () =>
  useMutation({ mutationFn: (form: FormData) => api.upload<ChartAnalyzeResult>("/charts/analyze", form) });

export function useWatchlistMutations() {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["watchlists"] });
  return {
    create: useMutation({ mutationFn: (name: string) => api.post<Watchlist>("/watchlists", { name }), onSuccess: done }),
    remove: useMutation({ mutationFn: (id: number) => api.del(`/watchlists/${id}`), onSuccess: done }),
    addItem: useMutation({
      mutationFn: (v: { id: number; symbol: string }) => api.post<Watchlist>(`/watchlists/${v.id}/items`, { symbol: v.symbol }),
      onSuccess: done,
    }),
    removeItem: useMutation({ mutationFn: (v: { id: number; itemId: number }) => api.del(`/watchlists/${v.id}/items/${v.itemId}`), onSuccess: done }),
  };
}

// ---- Trade Opportunities ----
export const useOppSummary = () => {
  const x = useExperimental();
  return useQuery({
    queryKey: ["opp-summary", x],
    queryFn: () => api.get<OppSummary>("/opportunities/summary", expParam(x)),
    refetchInterval: (q) => (q.state.data?.running_scan ? 2000 : 60_000),
    retry: retryPolicy,
  });
};
export const useOpportunity = (id: number | null) => {
  const x = useExperimental();
  return useQuery({
    queryKey: ["opportunity", id, x],
    queryFn: () => api.get<OpportunityDetail>(`/opportunities/${id}`, expParam(x)),
    enabled: id !== null,
    retry: retryPolicy,
  });
};
export const useOppValidation = () => useQuery({ queryKey: ["opp-validation"], queryFn: () => api.get<OppValidation>("/opportunities/validation"), staleTime: 300_000 });

export function useStartScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: { symbols?: string[]; refresh_data?: boolean }) => api.post<ScanAccepted>("/opportunities/scan", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opp-summary"] }),
  });
}

// ---- Signals (top-down multi-timeframe engine) ----
export const useSignalsSummary = () => {
  const x = useExperimental();
  return useQuery({ queryKey: ["signals", x], queryFn: () => api.get<SignalsSummary>("/signals", expParam(x)), refetchInterval: 60_000, retry: retryPolicy });
};

export const useSignal = (symbol: string | null) => {
  const x = useExperimental();
  return useQuery({
    queryKey: ["signal", symbol, x],
    queryFn: () => api.get<SignalAnalysis>(`/signals/${symbol}`, expParam(x)),
    enabled: !!symbol,
    refetchInterval: 60_000,
    placeholderData: keepPreviousData,
    retry: retryPolicy,
  });
};

/** Candles from the SAME provider the signal engine used for this instrument (never mixed). */
export const useSignalCandles = (symbol: string, timeframe: string, provider: string, enabled = true) =>
  useQuery({
    queryKey: ["signal-candles", symbol, timeframe, provider],
    queryFn: () => api.get<CandlesResponse>("/market/candles", { symbol, timeframe, provider, limit: 300 }),
    enabled,
    placeholderData: keepPreviousData,
    retry: retryPolicy,
  });

export function useSyncSignal() {
  const qc = useQueryClient();
  const x = useExperimental();
  return useMutation({
    mutationFn: (symbol: string) => api.post<SignalSync>(`/signals/${symbol}/sync${x ? "?experimental=true" : ""}`),
    onSuccess: (d, symbol) => {
      qc.setQueryData(["signal", symbol, x], d.analysis);
      void qc.invalidateQueries({ queryKey: ["signals"] });
      void qc.invalidateQueries({ queryKey: ["signal-candles", symbol] });
    },
  });
}

// ---- Paper trading (simulated orders on live candles) ----
export const usePaperSummary = () =>
  useQuery({ queryKey: ["paper-summary"], queryFn: () => api.get<PaperSummary>("/paper/summary"), refetchInterval: 30_000, retry: retryPolicy });

export const usePaperTrades = (status: string) =>
  useQuery({
    queryKey: ["paper-trades", status],
    queryFn: () => api.get<PaperTradesPage>("/paper/trades", { status, limit: 200 }),
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
    retry: retryPolicy,
  });

export const usePaperTrade = (id: number | null) =>
  useQuery({ queryKey: ["paper-trade", id], queryFn: () => api.get<PaperTradeDetail>(`/paper/trades/${id}`), enabled: id !== null, retry: retryPolicy });

function invalidatePaper(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ["paper-summary"] });
  void qc.invalidateQueries({ queryKey: ["paper-trades"] });
}

export function useRunPaperCycle() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => api.post<PaperRunResult>("/paper/run"), onSuccess: () => invalidatePaper(qc) });
}

export function useUpdatePaperAccount() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (c: PaperAccountChanges) => api.patch<PaperAccount>("/paper/account", c), onSuccess: () => invalidatePaper(qc) });
}

export function useResetPaperAccount() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (c: PaperAccountChanges) => api.post<PaperAccount>("/paper/account/reset", c), onSuccess: () => invalidatePaper(qc) });
}

// ---- Gold Research (historical study; refreshed when the research pipeline rebuilds its summary) ----
export const useGoldResearch = () =>
  useQuery({ queryKey: ["gold-research"], queryFn: () => api.get<GoldResearch>("/research/gold"), staleTime: 300_000, retry: retryPolicy });

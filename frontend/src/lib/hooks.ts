"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "@/lib/api";
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
  PatternsResponse,
  Prediction,
  PredictionDetail,
  PredictionStats,
  ProviderInfo,
  Quote,
  Timeframe,
  Watchlist,
} from "@/lib/types";

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
export const usePatternDefinitions = () =>
  useQuery({ queryKey: ["pattern-defs"], queryFn: () => api.get<PatternDefinitions>("/patterns/definitions"), staleTime: Infinity });

export const useAnalysis = (id: number | null) =>
  useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api.get<Analysis>(`/analysis/${id}`),
    enabled: id !== null,
    refetchInterval: (q) => (isActive(q.state.data?.status) ? 1500 : false),
  });
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
export const usePredictions = (f: PredictionFilters = {}) =>
  useQuery({
    queryKey: ["predictions", f],
    queryFn: () => api.get<Page<Prediction>>("/predictions", { limit: 25, ...f }),
    placeholderData: keepPreviousData,
  });
export const usePrediction = (id: number) =>
  useQuery({ queryKey: ["prediction", id], queryFn: () => api.get<PredictionDetail>(`/predictions/${id}`), retry: retryPolicy });
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

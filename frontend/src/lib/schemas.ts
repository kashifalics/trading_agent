import { z } from "zod";
import { TIMEFRAME_CODES } from "@/lib/utils";

const tf = z.string().refine((v) => TIMEFRAME_CODES.includes(v), "Unsupported timeframe");
const optionalNumber = z.preprocess((v) => (v === "" || v === null || v === undefined ? undefined : Number(v)), z.number().finite().optional());

export const analysisSchema = z.object({
  symbol: z.string().min(3, "Choose an instrument"),
  timeframe: tf,
  higher: z.string().optional(),
  intermediate: z.string().optional(),
  entry: z.string().optional(),
  lookback_bars: z.coerce.number().int().min(200, "Minimum 200 bars").max(20000, "Maximum 20,000 bars"),
  auto_sync: z.boolean(),
});
export type AnalysisForm = z.infer<typeof analysisSchema>;

export const uploadSchema = z
  .object({
    symbol: z.string().optional(),
    timeframe: z.string().optional(),
    y1: optionalNumber,
    p1: optionalNumber,
    y2: optionalNumber,
    p2: optionalNumber,
  })
  .superRefine((v, ctx) => {
    const set = [v.y1, v.p1, v.y2, v.p2].filter((x) => x !== undefined).length;
    if (set !== 0 && set !== 4) ctx.addIssue({ code: "custom", message: "Provide both calibration points (row + price each), or none", path: ["y1"] });
    if (set === 4 && v.y1 === v.y2) ctx.addIssue({ code: "custom", message: "Calibration rows must differ", path: ["y2"] });
    if (v.timeframe && !TIMEFRAME_CODES.includes(v.timeframe)) ctx.addIssue({ code: "custom", message: "Unsupported timeframe", path: ["timeframe"] });
  });
export type UploadForm = z.infer<typeof uploadSchema>;

export const backtestSchema = z.object({
  symbol: z.string().min(3),
  timeframe: tf,
  strategy: z.string().min(1),
  bars: z.coerce.number().int().min(300, "Minimum 300 bars").max(50000),
  risk_pct: z.coerce.number().gt(0, "Must be > 0").max(10, "Max 10%"),
  spread: z.coerce.number().min(0),
  slippage: z.coerce.number().min(0),
  commission_pct: z.coerce.number().min(0).max(5),
  eval_every: z.coerce.number().int().min(1).max(100),
});
export type BacktestForm = z.infer<typeof backtestSchema>;

export const trainSchema = z.object({
  symbol: z.string().min(3),
  timeframe: tf,
  algorithm: z.enum(["logistic", "lightgbm", "xgboost"]),
  bars: z.coerce.number().int().min(1000, "Minimum 1,000 bars").max(100000),
  spread: z.coerce.number().min(0),
  horizon_bars: z.coerce.number().int().min(4).max(200),
});
export type TrainForm = z.infer<typeof trainSchema>;

// Shared chart types and colours. The functions that turn analysis events into drawings live in ./overlay-build.ts.

export interface ChartMarker {
  time: number;
  position: "aboveBar" | "belowBar" | "inBar";
  shape: "circle" | "square" | "arrowUp" | "arrowDown";
  color: string;
  text: string;
}

export interface ChartZone {
  from: number; // epoch seconds (origin bar)
  low: number;
  high: number;
  color: string;
  border?: string;
  label: string;
}

/** A horizontal level between two bars (e.g. the swing a BOS broke, from the swing bar to the breaking bar). */
export interface ChartSegment {
  from: number;
  to: number;
  price: number;
  color: string;
  label: string;
  dashed?: boolean;
  above?: boolean; // label above (true) or below the line
}

export interface ChartLine {
  price: number;
  color: string;
  title: string;
  dashed?: boolean;
}

export const COLORS = {
  bull: "#4caf50",
  bear: "#ef5350",
  neutral: "#8a94a6",
  warn: "#f59e0b",
  primary: "#3b5bdb",
};

export const dirColor = (d: string) => (d === "bullish" ? COLORS.bull : d === "bearish" ? COLORS.bear : COLORS.neutral);

export const rgba = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

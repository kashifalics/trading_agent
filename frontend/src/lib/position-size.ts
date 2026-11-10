// Position size from the plan's actual stop distance. Contract sizes differ between brokers: the defaults are common CFD specs
// (XAUUSD 100 oz per lot, BTC 1 coin per lot, US30 1 index unit, USOIL 1000 barrels, FX 100,000 units) and are editable on the page.

export const DEFAULT_CONTRACT_SIZE: Record<string, number> = { XAUUSD: 100, BTCUSDT: 1, BTCUSD: 1, US30: 1, USOIL: 1000, EURUSD: 100000, GBPUSD: 100000 };

export interface PositionSize {
  riskAmount: number;
  units: number;
  lots: number;
  stopDistance: number;
}

export function positionSize(balance: number, riskPct: number, entry: number, stop: number, contractSize: number): PositionSize | null {
  const stopDistance = Math.abs(entry - stop);
  if (!(balance > 0) || !(riskPct > 0) || !(stopDistance > 0) || !(contractSize > 0)) return null;
  const riskAmount = (balance * riskPct) / 100;
  const units = riskAmount / stopDistance;
  return { riskAmount, units, lots: units / contractSize, stopDistance };
}

# Roadmap

Ordered by value for getting to a trustworthy system. Statuses live in `IMPLEMENTATION_STATUS.md`.

## Next (unblocks real evaluation)
1. **Data for XAUUSD** — add a free Twelve Data key, run `/market/coverage/probe`, record what the free plan really serves.
2. **Deep history for BTCUSDT** — ingest ≥ 3 years of 1H/4H (paginated sync already supports it) so walk-forward validation has enough rows/regimes; re-run model training and the backtest with realistic costs (BTCUSDT spread ≈ 0.01, ~0.075% taker fee).
3. **US30 / USOIL feed** — implement a licensed `MarketDataProvider` (broker API or paid data); the mapping/UI already treats them as unsupported until then.
4. **Strategy research loop** — the current rule set lost money in the first sample. Evaluate ablations (which evidence categories carry signal?), use a held-out period, avoid tuning on the test window.

## Then
* Auth: user registration + key issuance endpoint/UI, cookie sessions.
* Redis-backed rate limiting and quote cache; Prometheus metrics; Sentry wiring.
* Paper trading (simulated fills against live quotes) — explicitly out of scope until validation exists.
* Vision: time-axis OCR for candle timestamps, hollow/black-white candle themes, log price scale, optional vision-LLM *explanations only* (never numbers).
* Multi-timeframe: richer alignment (premium/discount confluence across TFs), regime classifier.
* Model monitoring: drift and live calibration tracking vs stored predictions.
* Candle sessions: holiday calendars, maintenance windows, session-anchored 4H.
* Frontend: server-side event overlays for all timeframes, saved analysis layouts, CSV export.

## Explicitly not planned
Automatic order execution, broker account connectivity, scraping of unlicensed data.

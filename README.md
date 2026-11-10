# AI Trading Intelligence

An **analysis and decision-support tool** for gold (XAUUSD), forex (EURUSD, GBPUSD), Bitcoin (BTCUSDT), the Dow (US30) and oil
(USOIL). It reads market candles, detects price-action structure on 14 timeframes, and shows possible trade setups with their entry,
stop loss, targets and the reasons for and against them.

> **Analysis only.** The product never places orders and is not connected to any broker or trading account.
>
> **No validated edge.** None of its strategies or models has passed out-of-sample validation (see
> [What the research found](#what-the-research-found)). Every BUY/SELL setup is labelled **Not validated**, no win probability is
> shown, and the setup score measures quality, not the chance of winning.

## What it does

* **Signals:** top-down analysis of every timeframe (higher-timeframe bias → structural setup → lower-timeframe confirmation), with a
  clear instruction (EXECUTE NOW, PLACE LIMIT ORDER, WAIT FOR CONFIRMATION or NO TRADE), entry, stop, up to three targets
  (minimum 1:2 reward-to-risk), a 100-point quality checklist and a position-size calculator.
* **Paper trading:** records every signal the moment it appears and follows it on later candles with simulated orders, so you can
  see how the rules behave going forward. No verdict before 100 closed trades.
* **Trade Opportunities:** setups ranked across instruments and trading styles (scalping, intraday, swing, long-term).
* **Chart analysis, patterns, predictions, backtesting** and the results of a 20-year gold study.
* **Safety rules built in:** WAIT/NO TRADE whenever evidence is weak, data is stale or incomplete, the stop is not structural or a
  1:2 target is not reachable; delayed prices are marked as delayed; unsupported data is reported, never invented.

Not included: automatic trading, broker connections, an AI chat assistant, TradingView/Pine Script integration, a news filter.

## Getting started

**Use a hosted installation:** open the address you were given, go to **Settings**, enter your platform API key and press
**Save & verify**. Then open **Signals** and press **Refresh now**.

**Install it yourself (Docker):**
```powershell
.\scripts\setup.ps1 -DockerOnly        # bash: ./scripts/setup.sh --docker-only  (creates .env with generated secrets)
docker compose up --build              # UI http://localhost:3000 · API reference http://localhost:8000/docs
```
Without Docker, with your own production settings, and for deployment, follow the
[Technical handover](docs/TECHNICAL_HANDOVER.md). No paid service is required: the default market data sources are free and need no
key (an optional Twelve Data or OANDA key adds alternative sources).

## Documentation

| For | Document |
|---|---|
| Using the product | [User guide](docs/USER_GUIDE.md) |
| Installing, configuring, deploying, maintaining | [Technical handover](docs/TECHNICAL_HANDOVER.md), [Local setup](docs/LOCAL_SETUP.md) |
| API | [API specification](docs/API_SPECIFICATION.md) and `/docs` on the backend |
| Security | [Security](docs/SECURITY.md) |
| How it works | [Architecture](docs/ARCHITECTURE.md), [Signal engine](docs/SIGNAL_ENGINE.md), [Paper trading](docs/PAPER_TRADING.md), [Data providers](docs/MARKET_DATA_PROVIDERS.md) |
| Current status | [Implementation status](docs/IMPLEMENTATION_STATUS.md) |

## What the research found

The rules and models in this product were tested on history before release, and none showed a reliable advantage:
* The signal rules, replayed on Bitcoin and gold: −0.048 R per trade after spread overall, −0.19 R on the out-of-sample part
  ([track record](docs/reports/SIGNAL_TRACK_RECORD.md)).
* About 600 price patterns per instrument on every timeframe: none confirmed ([gold](docs/reports/PATTERN_EDGE_XAUUSD.md),
  [Bitcoin](docs/reports/PATTERN_EDGE_BTCUSDT.md)).
* A 20-year study of 1-minute gold data: 1,931 pattern hypotheses and 36 further structural tests; 0 confirmed on independent
  data, and no machine-learning model good enough to promote ([audit](docs/reports/XAUUSD_RESEARCH_AUDIT.md),
  [experiment 2](docs/reports/XAUUSD_EXPERIMENT2.md)).

This does not prove that no edge exists; it means none has been demonstrated. Use the product to structure your own analysis.

---

_Not financial advice. Past patterns do not guarantee future results. Never risk money you cannot afford to lose._

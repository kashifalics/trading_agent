"""Central trading decision: one of ENTER, HOLD, WAIT, EXIT or NO TRADE for every instrument x timeframe, used by every page.

`core.decide` is the only place that turns analysis into a customer call; `adapters` translate each module's native output (signal
engine plans, trade opportunities, decision-engine predictions) into its input; `core.manage_trade` handles tracked paper trades.
Analysis only: nothing here places or simulates an order."""

def explain(decision: str, symbol: str, timeframe: str, confluence: float | None, evidence: list[dict],
            wait_reasons: list[str], plan: dict | None, warnings: list[str]) -> str:
    """Deterministic, template-based explanation (works with no LLM)."""
    lines = []
    if decision == "WAIT":
        lines.append(f"WAIT on {symbol} {timeframe}: no trade is justified by the current evidence.")
        lines += [f"- {r}" for r in wait_reasons]
    else:
        lines.append(f"{decision} setup on {symbol} {timeframe} (analytical confluence {confluence:+.2f}).")
    ranked = sorted((e for e in evidence if e["weight"] > 0), key=lambda e: -abs(e["score"]))
    sign = 1 if decision == "BUY" else -1 if decision == "SELL" else (1 if (confluence or 0) >= 0 else -1)
    pro = [e for e in ranked if e["score"] * sign > 0][:4]
    con = [e for e in ranked if e["score"] * sign < 0][:3]
    if pro:
        lines.append("Supporting" + (" (leaning)" if decision == "WAIT" else "") + ":")
        lines += [f"- {e['name']}: {e['detail']}" for e in pro]
    if con:
        lines.append("Against:")
        lines += [f"- {e['name']}: {e['detail']}" for e in con]
    if plan:
        lines.append(f"Plan: entry {plan['entry_low']:.6g}-{plan['entry_high']:.6g}, stop {plan['stop_loss']:.6g}, "
                     f"targets {', '.join(f'{t:.6g}' for t in plan['targets'])}, R:R {plan['risk_reward']:.2f}.")
    if warnings:
        lines.append("Caveats: " + "; ".join(warnings))
    lines.append("Analysis only - not financial advice; nothing is executed.")
    return "\n".join(lines)

"""Rug / safety check: reject pairs that look illiquid, too new, or manipulated."""


def check(pid, bars, cfg, spread_pct=None):
    """Return (ok, reason)."""
    if len(bars) < cfg.min_history_bars:
        return False, f"only {len(bars)} bars of history (<{cfg.min_history_bars})"
    if spread_pct is not None and spread_pct > cfg.max_spread_pct:
        return False, f"spread {spread_pct:.2%} too wide"
    for b in bars[-48:]:
        if b["open"] > 0 and abs(b["close"] / b["open"] - 1) > cfg.max_bar_move_pct:
            return False, "recent candle moved >25% (pump/dump risk)"
    if sum(1 for b in bars[-48:] if b["volume"] == 0) > 5:
        return False, "too many zero-volume candles"
    return True, "passed"

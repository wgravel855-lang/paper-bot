"""Trend-following breakout. Every decision returns a plain-English reason."""
from .indicators import ema, atr


def entry_signal(bars, cfg):
    """Look at the latest *closed* bar. Return (go, reason, atr_value)."""
    need = max(cfg.ema_slow, cfg.breakout_lookback, cfg.atr_period) + 2
    if len(bars) < need:
        return False, "not enough bars", None
    closes = [b["close"] for b in bars]
    fast, slow = ema(closes, cfg.ema_fast)[-1], ema(closes, cfg.ema_slow)[-1]
    a = atr(bars, cfg.atr_period)[-1]
    last = bars[-1]
    prior_high = max(b["high"] for b in bars[-cfg.breakout_lookback - 1:-1])
    avg_vol = sum(b["volume"] for b in bars[-21:-1]) / 20
    vol_x = last["volume"] / avg_vol if avg_vol else 0

    if fast <= slow:
        return False, "no uptrend (EMA20 <= EMA50)", a
    if last["close"] <= prior_high:
        return False, "no breakout", a
    if vol_x < cfg.volume_spike:
        return False, f"breakout on weak volume ({vol_x:.1f}x)", a
    reason = (f"BUY: close {last['close']:.6g} broke {cfg.breakout_lookback}-bar high "
              f"{prior_high:.6g}; uptrend EMA{cfg.ema_fast}>{cfg.ema_slow}; volume {vol_x:.1f}x avg")
    return True, reason, a


def exit_signal(pos, bars, cfg):
    """Update trailing stop and decide whether to exit. Return (go, reason)."""
    last = bars[-1]
    a = atr(bars, cfg.atr_period)[-1]
    pos["bars_held"] += 1
    # check the stop set by *previous* bars first (no peeking inside this bar)
    if last["low"] <= pos["stop"]:
        fill = min(pos["stop"], last["open"])   # gapped through the stop -> fill at open
        return True, f"SELL: trailing stop hit at {pos['stop']:.6g}", fill
    pos["high"] = max(pos["high"], last["high"])
    pos["stop"] = max(pos["stop"], pos["high"] - cfg.stop_atr * a)
    closes = [b["close"] for b in bars]
    if ema(closes, cfg.ema_fast)[-1] < ema(closes, cfg.ema_slow)[-1]:
        return True, "SELL: trend ended (EMA20 crossed below EMA50)", last["close"]
    if pos["bars_held"] >= cfg.max_hold_bars:
        return True, f"SELL: time stop ({cfg.max_hold_bars} bars)", last["close"]
    return False, "", None

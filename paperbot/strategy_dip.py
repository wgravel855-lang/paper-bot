"""Buy-the-dip (mean reversion), a common pattern in community bot strategies.

Buy:  long-term uptrend (close above its 200-bar average) AND a sharp short-term drop
      (close below the lower Bollinger band, and RSI under 35).
Sell: price recovers to its 20-bar average, OR a fixed stop 2.5 ATR below entry,
      OR 12 bars (3 days on 6h candles) pass without a recovery.
"""
from .indicators import ema, atr


def _rsi(closes, n=14):
    gains = losses = 0.0
    g = l = None
    for a, b in zip(closes, closes[1:]):
        d = b - a
        up, dn = max(d, 0), max(-d, 0)
        g = up if g is None else (g * (n - 1) + up) / n
        l = dn if l is None else (l * (n - 1) + dn) / n
    if not l:
        return 100.0
    return 100 - 100 / (1 + g / l)


def _bands(closes, n=20, k=2.0):
    w = closes[-n:]
    m = sum(w) / n
    sd = (sum((x - m) ** 2 for x in w) / n) ** 0.5
    return m - k * sd, m, m + k * sd


def entry_signal(bars, cfg):
    if len(bars) < 210:
        return False, "not enough bars", None
    closes = [b["close"] for b in bars]
    c = closes[-1]
    trend = ema(closes, 200)[-1]
    lower, mid, _ = _bands(closes)
    rsi = _rsi(closes[-100:])
    a = atr(bars, cfg.atr_period)[-1]
    if c <= trend:
        return False, "not in long-term uptrend", a
    if c >= lower or rsi >= 35:
        return False, "no dip", a
    reason = (f"BUY THE DIP: close {c:.6g} below lower band {lower:.6g}, RSI {rsi:.0f}, "
              f"still above 200-bar average {trend:.6g}; target 20-bar average {mid:.6g}")
    return True, reason, a


def exit_signal(pos, bars, cfg):
    last = bars[-1]
    pos["bars_held"] += 1
    if last["low"] <= pos["stop"]:
        return True, f"SELL: stop hit at {pos['stop']:.6g}", min(pos["stop"], last["open"])
    _, mid, _ = _bands([b["close"] for b in bars])
    if last["close"] >= mid:
        return True, f"SELL: bounced back to 20-bar average {mid:.6g}", last["close"]
    if pos["bars_held"] >= 12:
        return True, "SELL: no bounce within 3 days", last["close"]
    return False, "", None

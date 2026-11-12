"""Features the ML model sees, built from HOURLY candles.
Every value uses only data up to and including that hour's close."""
import numpy as np
import pandas as pd

FEATURES = ["ret_1", "ret_6", "ret_24", "ret_72", "ret_168", "vol_ratio", "atr_pct",
            "dist_ema24", "trend_24_96", "breakout_dist", "drawdown_30d", "rsi_14",
            "btc_ret_24", "btc_trend", "hour"]

NAMES = {  # plain-English names for the dashboard
    "ret_1": "Last-hour return", "ret_6": "6-hour momentum", "ret_24": "1-day momentum",
    "ret_72": "3-day momentum", "ret_168": "1-week momentum", "vol_ratio": "Volume surge (last 6h)",
    "atr_pct": "Volatility", "dist_ema24": "Distance from 1-day average",
    "trend_24_96": "Trend strength (1-day vs 4-day average)", "breakout_dist": "Distance from 5-day high",
    "drawdown_30d": "Drop from 30-day high", "rsi_14": "RSI (overbought/oversold)",
    "btc_ret_24": "Bitcoin 1-day momentum", "btc_trend": "Bitcoin trend", "hour": "Time of day",
}
HORIZON_H = 24          # predict 24 hours ahead
TARGET = 0.015          # "+1.5%": roughly what's needed to beat round-trip costs


def _frame(bars):
    df = pd.DataFrame(bars).set_index("t").sort_index()
    return df[~df.index.duplicated()]


def frame(bars, btc_bars):
    df = _frame(bars)
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    out = pd.DataFrame(index=df.index)
    for n in (1, 6, 24, 72, 168):
        out[f"ret_{n}"] = np.log(c / c.shift(n))
    out["vol_ratio"] = v.rolling(6).sum() / (v.rolling(168).sum().shift(6) / 28)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    out["atr_pct"] = tr.ewm(span=24, adjust=False).mean() / c
    e24, e96 = c.ewm(span=24, adjust=False).mean(), c.ewm(span=96, adjust=False).mean()
    out["dist_ema24"] = c / e24 - 1
    out["trend_24_96"] = e24 / e96 - 1
    out["breakout_dist"] = c / h.rolling(120).max().shift(1) - 1
    out["drawdown_30d"] = c / h.rolling(720, min_periods=168).max() - 1
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi_14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    b = _frame(btc_bars)["close"].reindex(df.index).ffill()
    out["btc_ret_24"] = np.log(b / b.shift(24))
    out["btc_trend"] = b.ewm(span=24, adjust=False).mean() / b.ewm(span=96, adjust=False).mean() - 1
    out["hour"] = (out.index % 86400) // 3600
    out["close"] = c
    return out.replace([np.inf, -np.inf], np.nan)


def label(fr):
    fwd = fr["close"].shift(-HORIZON_H) / fr["close"] - 1
    return (fwd > TARGET).astype(float).where(fwd.notna()), fwd

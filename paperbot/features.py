"""Features the ML model sees. Every value uses only data up to and including that bar's close."""
import numpy as np
import pandas as pd

FEATURES = ["ret_1", "ret_4", "ret_12", "ret_28", "vol_ratio", "atr_pct", "dist_ema20",
            "trend_20_50", "breakout_dist", "rsi_14", "btc_ret_4", "btc_trend", "hour"]

NAMES = {  # plain-English names for the dashboard
    "ret_1": "Last-candle return", "ret_4": "1-day momentum", "ret_12": "3-day momentum",
    "ret_28": "1-week momentum", "vol_ratio": "Volume surge", "atr_pct": "Volatility",
    "dist_ema20": "Distance from 20-bar average", "trend_20_50": "Trend strength (EMA20 vs EMA50)",
    "breakout_dist": "Distance from 20-bar high", "rsi_14": "RSI (overbought/oversold)",
    "btc_ret_4": "Bitcoin 1-day momentum", "btc_trend": "Bitcoin trend", "hour": "Time of day",
}


def _frame(bars):
    df = pd.DataFrame(bars).set_index("t").sort_index()
    return df[~df.index.duplicated()]


def frame(bars, btc_bars):
    df = _frame(bars)
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    out = pd.DataFrame(index=df.index)
    for n in (1, 4, 12, 28):
        out[f"ret_{n}"] = np.log(c / c.shift(n))
    out["vol_ratio"] = v / v.rolling(20).mean().shift(1)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    out["atr_pct"] = tr.ewm(span=14, adjust=False).mean() / c
    e20, e50 = c.ewm(span=20, adjust=False).mean(), c.ewm(span=50, adjust=False).mean()
    out["dist_ema20"] = c / e20 - 1
    out["trend_20_50"] = e20 / e50 - 1
    out["breakout_dist"] = c / h.rolling(20).max().shift(1) - 1
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi_14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    b = _frame(btc_bars)["close"].reindex(df.index).ffill()
    out["btc_ret_4"] = np.log(b / b.shift(4))
    out["btc_trend"] = b.ewm(span=20, adjust=False).mean() / b.ewm(span=50, adjust=False).mean() - 1
    out["hour"] = (out.index % 86400) // 3600
    out["close"] = c
    return out.replace([np.inf, -np.inf], np.nan)


def label(fr, horizon=4, threshold=0.015):
    """1 if price is >1.5% higher `horizon` bars later (enough to beat round-trip costs)."""
    fwd = fr["close"].shift(-horizon) / fr["close"] - 1
    return (fwd > threshold).astype(float).where(fwd.notna()), fwd

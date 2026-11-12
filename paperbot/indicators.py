def ema(values, n):
    k, out, e = 2 / (n + 1), [], None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def atr(bars, n):
    trs, prev = [], None
    for b in bars:
        tr = b["high"] - b["low"] if prev is None else max(
            b["high"] - b["low"], abs(b["high"] - prev), abs(b["low"] - prev))
        trs.append(tr)
        prev = b["close"]
    return ema(trs, n)

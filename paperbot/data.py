"""Market data from Coinbase's public API (no account or keys needed)."""
import time
import requests

BASE = "https://api.exchange.coinbase.com"
_session = requests.Session()
_session.headers["User-Agent"] = "paperbot/0.1"
_last_call = 0.0


def _get(path, params=None, retries=4):
    global _last_call
    for attempt in range(retries):
        wait = 0.15 - (time.time() - _last_call)   # stay under public rate limit
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        try:
            r = _session.get(BASE + path, params=params, timeout=15)
            if r.status_code == 429:
                time.sleep(1 + attempt)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(1 + attempt)


def products(quote="USD"):
    out = []
    for p in _get("/products"):
        if p.get("quote_currency") != quote or p.get("status") != "online":
            continue
        if p.get("trading_disabled") or p.get("cancel_only") or p.get("auction_mode"):
            continue
        out.append(p["id"])
    return sorted(out)


def stats(pid):
    """24h open/high/low/last/volume."""
    s = _get(f"/products/{pid}/stats")
    return {k: float(s[k]) for k in ("open", "high", "low", "last", "volume") if s.get(k)}


def ticker(pid):
    t = _get(f"/products/{pid}/ticker")
    return {"bid": float(t["bid"]), "ask": float(t["ask"]), "price": float(t["price"])}


def candles(pid, granularity=3600, bars=300, end=None):
    """Return list of dicts oldest->newest. Pages backwards 300 bars at a time."""
    end = int(end or time.time())
    out = {}
    while len(out) < bars:
        n = min(300, bars - len(out))
        start = end - n * granularity
        rows = _get(f"/products/{pid}/candles", {
            "granularity": granularity,
            "start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
            "end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end)),
        })
        if not rows:
            break
        for t, lo, hi, op, cl, vol in rows:
            out[t] = {"t": t, "open": op, "high": hi, "low": lo, "close": cl, "volume": vol}
        end = start
    return [out[k] for k in sorted(out)][-bars:]


# ---------------------------------------------------------------- on-disk cache
import json as _json
import os as _os

CACHE_DIR = "data/cache"


def candles_cached(pid, granularity, bars):
    """Like candles(), but keeps a local copy and only downloads what's new.
    Returns closed candles only, oldest -> newest."""
    _os.makedirs(CACHE_DIR, exist_ok=True)
    path = _os.path.join(CACHE_DIR, f"{pid}_{granularity}.json")
    have = []
    if _os.path.exists(path):
        try:
            with open(path) as f:
                have = [dict(zip(("t", "open", "high", "low", "close", "volume"), r)) for r in _json.load(f)]
        except (ValueError, OSError):
            have = []
    now = int(time.time())
    want_start = now - bars * granularity
    if have and have[0]["t"] <= want_start + 7 * 86400:
        missing = (now - have[-1]["t"]) // granularity + 2
        new = candles(pid, granularity, missing) if missing > 1 else []
    else:
        new = candles(pid, granularity, bars)
    merged = {b["t"]: b for b in have}
    merged.update({b["t"]: b for b in new})
    out = [merged[k] for k in sorted(merged) if k >= want_start - granularity]
    out = [b for b in out if b["t"] + granularity <= now]        # closed candles only
    with open(path, "w") as f:
        _json.dump([[b["t"], b["open"], b["high"], b["low"], b["close"], b["volume"]] for b in out], f)
    return out

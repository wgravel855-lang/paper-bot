"""Scanner: find the most liquid USD pairs worth watching."""
from . import data


def scan(cfg, log=print):
    ids = [p for p in data.products(cfg.quote)
           if p.split("-")[0] not in cfg.stablecoins and p not in cfg.excluded]
    log(f"[scanner] {len(ids)} {cfg.quote} pairs online, checking 24h volume...")
    ranked = []
    for pid in ids:
        try:
            s = data.stats(pid)
        except Exception:
            continue
        usd_vol = s.get("volume", 0) * s.get("last", 0)
        if usd_vol >= cfg.min_24h_usd_volume:
            ranked.append((usd_vol, pid))
    ranked.sort(reverse=True)
    universe = [pid for _, pid in ranked[: cfg.universe_size]]
    log(f"[scanner] universe: {', '.join(universe)}")
    return universe

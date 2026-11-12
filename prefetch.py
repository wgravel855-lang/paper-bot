"""Download (or top up) the training data cache. Used by train.py; can be run alone."""
import sys
import time

from paperbot import data, scanner
from paperbot.config import Config

ML_UNIVERSE, HISTORY_DAYS = 40, 1530


def fetch_all(log=print):
    cfg = Config()
    cfg.universe_size = ML_UNIVERSE
    cfg.min_24h_usd_volume = 1_000_000
    ml_universe = scanner.scan(cfg, log)
    if "BTC-USD" not in ml_universe:
        ml_universe.insert(0, "BTC-USD")
    h6, h1 = {}, {}
    for i, pid in enumerate(ml_universe):
        t = time.time()
        h1[pid] = data.candles_cached(pid, 3600, HISTORY_DAYS * 24)
        if i < 16 or pid == "BTC-USD":
            h6[pid] = data.candles_cached(pid, 21600, HISTORY_DAYS * 4 + 300)
        log(f"[data] {i + 1}/{len(ml_universe)} {pid}: {len(h1[pid])} hourly candles ({time.time() - t:.0f}s)")
    return ml_universe, h1, h6


if __name__ == "__main__":
    fetch_all(lambda m: print(m, flush=True))
    sys.exit(0)

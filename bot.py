"""Live PAPER trading for three accounts side by side, on real Coinbase prices.
No real money, no real orders.

    python bot.py --once     # one cycle (what GitHub Actions runs hourly)
    python bot.py            # loop forever
    python bot.py --reset    # wipe all three paper accounts
"""
import argparse
import csv
import glob
import json
import os
import time

from paperbot import data, scanner, dashboard
from paperbot.accounts import ACCOUNTS, make
from paperbot.config import Config
from paperbot.engine import step
from paperbot.executor import Portfolio
from paperbot.logger import Logger, save_state, load_state

SHARED = "data/live_shared.json"
PRED = "data/live_ml_predictions.csv"
PRED_FIELDS = ["bar_time", "pair", "prob", "approved", "close", "ret_24h"]


def closed_bars(pid, cfg):
    bars = data.candles(pid, cfg.granularity, 300)
    if bars and bars[-1]["t"] + cfg.granularity > time.time():
        bars = bars[:-1]
    return bars


def record_predictions(preds, history, gran, horizon=4):
    rows = list(csv.DictReader(open(PRED))) if os.path.exists(PRED) else []
    for p in preds:
        rows.append({"bar_time": p["bar_t"], "pair": p["pair"], "prob": f"{p['prob']:.4f}",
                     "approved": int(p["approved"]), "close": p["close"], "ret_24h": ""})
    for r in rows:                         # fill in what actually happened 24h later
        if r["ret_24h"] == "" and r["pair"] in history:
            target = int(r["bar_time"]) + horizon * gran
            later = [b for b in history[r["pair"]] if b["t"] == target]
            if later:
                r["ret_24h"] = f"{later[0]['close'] / float(r['close']) - 1:.5f}"
    with open(PRED, "w", newline="") as f:
        w = csv.DictWriter(f, PRED_FIELDS)
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    base = Config()
    os.makedirs(base.data_dir, exist_ok=True)
    if args.reset:
        for p in glob.glob("data/live_*"):
            os.remove(p)

    shared = load_state(SHARED) or {}
    last_bar, universe = shared.get("last_bar", {}), shared.get("universe", [])
    scanned_at = shared.get("scanned_at", 0)

    while True:
        accts = {}
        for name in ACCOUNTS:
            cfg, gate = make(name)
            log = Logger(base.data_dir, f"live_{name}_")
            pf = Portfolio(cfg.starting_cash, cfg)
            st = load_state(f"data/live_{name}_state.json")
            if st:
                pf.cash, pf.positions = st["cash"], st["positions"]
            else:
                log.equity(time.time(), cfg.starting_cash)
            accts[name] = (cfg, gate, log, pf)
        try:
            if time.time() - scanned_at > 6 * 3600 or not universe:
                universe, scanned_at = scanner.scan(base, print), time.time()
            open_pairs = {p for (_, _, _, pf) in accts.values() for p in pf.positions}
            watch = sorted(set(universe) | open_pairs | {"BTC-USD"})
            all_bars, history, quotes = {}, {}, {}
            for pid in watch:
                bars = closed_bars(pid, base)
                all_bars[pid] = bars
                if bars and last_bar.get(pid) != bars[-1]["t"]:
                    history[pid] = bars
                    quotes[pid] = data.ticker(pid)
                    last_bar[pid] = bars[-1]["t"]
            if history:
                now = time.time()
                preds = []
                for name, (cfg, gate, log, pf) in accts.items():
                    if gate is not None:
                        gate.btc = all_bars.get("BTC-USD")
                    tradeable = {k: v for k, v in history.items() if k in universe or k in pf.positions}
                    eq = step(now, tradeable, pf, cfg, log, quotes, gate=gate, equity_on_close=False)
                    log.equity(now, eq)
                    save_state(f"data/live_{name}_state.json", pf)
                    log.activity(f"[{name}] equity ${eq:,.2f}; open: {', '.join(pf.positions) or 'none'}")
                    if gate is not None:
                        preds = gate.predictions
                record_predictions(preds, all_bars, base.granularity)
            else:
                print("[bot] no new closed candles since last run; nothing to do")
            save_state_shared(last_bar, universe, scanned_at)
            dashboard.build_compare("index.html", base)
        except Exception as e:
            print(f"[bot] error: {e!r} (will retry)")
        if args.once:
            break
        time.sleep(base.loop_seconds)


def save_state_shared(last_bar, universe, scanned_at):
    with open(SHARED, "w") as f:
        json.dump({"last_bar": last_bar, "universe": universe, "scanned_at": scanned_at,
                   "last_run": time.time()}, f, indent=1)


if __name__ == "__main__":
    main()

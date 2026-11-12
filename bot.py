"""Live PAPER trading loop. Uses real Coinbase prices; every trade is simulated.

    python bot.py            # runs forever, checks every 5 minutes
    python bot.py --once     # one cycle then exit
    python bot.py --reset    # wipe paper account and start over
"""
import argparse
import time

from paperbot import data, scanner, dashboard
from paperbot.config import Config
from paperbot.engine import step
from paperbot.executor import Portfolio
from paperbot.logger import Logger, save_state, load_state

STATE = "data/live_state.json"


def closed_bars(pid, cfg):
    bars = data.candles(pid, cfg.granularity, 300)
    if bars and bars[-1]["t"] + cfg.granularity > time.time():
        bars = bars[:-1]          # drop the still-forming candle
    return bars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    cfg = Config()
    log = Logger(cfg.data_dir, "live_")
    if args.reset:
        log.reset()
        import os
        if os.path.exists(STATE):
            os.remove(STATE)

    pf = Portfolio(cfg.starting_cash, cfg)
    universe, scanned_at, last_bar = [], 0, {}
    st = load_state(STATE)
    if st:
        pf.cash, pf.positions = st["cash"], st["positions"]
        last_bar = st.get("last_bar", {})
        log.activity(f"[bot] resumed: cash ${pf.cash:,.2f}, {len(pf.positions)} open positions")
    else:
        log.activity(f"[bot] new paper account with ${cfg.starting_cash:,.2f}")
        log.equity(time.time(), cfg.starting_cash)

    while True:
        try:
            if time.time() - scanned_at > 6 * 3600 or not universe:
                universe, scanned_at = scanner.scan(cfg, log.activity), time.time()
            watch = sorted(set(universe) | set(pf.positions))
            history, quotes = {}, {}
            for pid in watch:
                bars = closed_bars(pid, cfg)
                # only act once per newly closed candle per pair
                if bars and last_bar.get(pid) != bars[-1]["t"]:
                    history[pid] = bars
                    quotes[pid] = data.ticker(pid)
                    last_bar[pid] = bars[-1]["t"]
            if history:
                eq = step(time.time(), history, pf, cfg, log, quotes)
                log.activity(f"[bot] checked {len(history)} pairs; equity ${eq:,.2f}; "
                             f"open: {', '.join(pf.positions) or 'none'}")
                save_state(STATE, pf, last_bar)
                dashboard.build(cfg.data_dir, "live_", "Paper Bot: Live", cfg.starting_cash,
                                "index.html", None,
                                "<b>Paper trading</b> on live Coinbase prices. No real money, no real orders.",
                                refresh=60)
        except Exception as e:
            log.activity(f"[bot] error: {e!r} (will retry)")
        if args.once:
            break
        time.sleep(cfg.loop_seconds)


if __name__ == "__main__":
    main()

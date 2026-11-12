"""Backtest: replay history through the exact same engine the live bot uses.

    python backtest.py --days 120
"""
import argparse
import time

from paperbot import data, scanner, dashboard
from paperbot.config import Config
from paperbot.engine import step
from paperbot.executor import Portfolio
from paperbot.logger import Logger


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--cash", type=float, default=None)
    ap.add_argument("--granularity", type=int, default=None, help="candle seconds: 3600, 21600 or 86400")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    cfg = Config()
    if args.cash:
        cfg.starting_cash = args.cash
    if args.granularity:
        cfg.granularity = args.granularity

    universe = scanner.scan(cfg)
    warm = cfg.min_history_bars
    bars_needed = args.days * 86400 // cfg.granularity + warm
    hist = {}
    for pid in universe:
        b = data.candles(pid, cfg.granularity, bars_needed)
        print(f"[data] {pid}: {len(b)} bars")
        if len(b) > warm:
            hist[pid] = b
    log = Logger(cfg.data_dir, f"backtest{args.tag}_")
    log.reset()
    pf = Portfolio(cfg.starting_cash, cfg)

    timeline = sorted({b["t"] for bars in hist.values() for b in bars})[warm:]
    idx = {pid: {b["t"]: i for i, b in enumerate(bars)} for pid, bars in hist.items()}
    for t in timeline:
        view = {}
        for pid, bars in hist.items():
            i = idx[pid].get(t)
            if i is not None and i >= warm:
                view[pid] = bars[max(0, i - 299): i + 1]
        if view:
            step(t, view, pf, cfg, log)
    # close anything still open at the end so the result is fully realized
    last_prices = {pid: bars[-1]["close"] for pid, bars in hist.items()}
    for pid in list(pf.positions):
        tr = pf.sell(pid, last_prices[pid], "SELL: backtest ended", timeline[-1])
        log.trade(tr, pf.equity(last_prices))
        log.equity(timeline[-1], pf.equity(last_prices))

    btc = hist.get("BTC-USD")
    bench = None
    if btc:
        s = next(b for b in btc if b["t"] >= timeline[0])
        bench = btc[-1]["close"] / s["close"] - 1
    final = pf.equity(last_prices)
    period = f"{time.strftime('%Y-%m-%d', time.gmtime(timeline[0]))} to {time.strftime('%Y-%m-%d', time.gmtime(timeline[-1]))}"
    note = (f"<b>Backtest</b> on Coinbase {cfg.granularity // 3600}-hour candles, {period}, "
            f"{len(hist)} pairs. Includes {cfg.taker_fee:.2%} fee + {cfg.slippage:.2%} slippage per fill. "
            "Caveat: the pair list is today's most-liquid coins (survivorship bias), so real results would likely be worse.")
    out = dashboard.build(cfg.data_dir, f"backtest{args.tag}_", "Paper Bot: Backtest", cfg.starting_cash,
                          f"backtest{args.tag}_dashboard.html", bench, note)
    print(f"\nPeriod: {period}\nStart ${cfg.starting_cash:,.2f} -> End ${final:,.2f} ({final / cfg.starting_cash - 1:+.2%})")
    if bench is not None:
        print(f"Buy & hold BTC same period: {bench:+.2%}")
    print(f"Dashboard: {out}")


if __name__ == "__main__":
    main()

"""Logger: every trade written with its reason; equity curve on every close."""
import csv
import json
import os
import time

TRADE_FIELDS = ["time", "pair", "side", "qty", "price", "fee", "slippage_pct", "pnl", "equity", "reason"]


class Logger:
    def __init__(self, folder, prefix=""):
        os.makedirs(folder, exist_ok=True)
        self.trades_path = os.path.join(folder, prefix + "trades.csv")
        self.equity_path = os.path.join(folder, prefix + "equity.csv")
        self.activity_path = os.path.join(folder, prefix + "activity.log")

    def reset(self):
        for p in (self.trades_path, self.equity_path, self.activity_path):
            if os.path.exists(p):
                os.remove(p)

    def trade(self, tr, equity):
        new = not os.path.exists(self.trades_path)
        with open(self.trades_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(TRADE_FIELDS)
            w.writerow([_ts(tr["t"]), tr["pair"], tr["side"], f"{tr['qty']:.8g}", f"{tr['price']:.8g}",
                        f"{tr['fee']:.4f}", f"{tr['slippage_pct']:.4%}", f"{tr['pnl']:.2f}",
                        f"{equity:.2f}", tr["reason"]])

    def equity(self, t, equity):
        new = not os.path.exists(self.equity_path)
        with open(self.equity_path, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "equity"])
            w.writerow([_ts(t), f"{equity:.2f}"])

    def activity(self, msg):
        line = f"{_ts(time.time())} {msg}"
        print(line, flush=True)
        with open(self.activity_path, "a") as f:
            f.write(line + "\n")


def _ts(t):
    return time.strftime("%Y-%m-%d %H:%M", time.gmtime(t))


def save_state(path, portfolio, last_bar=None):
    with open(path, "w") as f:
        json.dump({"cash": portfolio.cash, "positions": portfolio.positions,
                   "last_bar": last_bar or {}}, f, indent=1)


def load_state(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

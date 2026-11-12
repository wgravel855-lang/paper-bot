"""Fast silent backtest used by training (same engine as live)."""
from .engine import step
from .executor import Portfolio


class NullLogger:
    def __init__(self):
        self.trades = []

    def trade(self, tr, equity):
        self.trades.append(tr)

    def equity(self, *a):
        pass

    def activity(self, *a):
        pass


def simulate(hist, cfg, t0, t1, gate=None, warm=200):
    """Run from time t0 to t1. Returns dict with return, max drawdown, trade count."""
    pf, log = Portfolio(1000.0, cfg), NullLogger()
    idx = {pid: {b["t"]: i for i, b in enumerate(bars)} for pid, bars in hist.items()}
    times = sorted({b["t"] for bars in hist.values() for b in bars if t0 <= b["t"] <= t1})
    peak, mdd, eq = 1000.0, 0.0, 1000.0
    for t in times:
        view = {}
        for pid, bars in hist.items():
            i = idx[pid].get(t)
            if i is not None and i >= warm:
                view[pid] = bars[max(0, i - 299): i + 1]
        if gate is not None and "BTC-USD" in hist:
            i = idx["BTC-USD"].get(t)
            gate.btc = hist["BTC-USD"][max(0, i - 149): i + 1] if i is not None else None
        if view:
            eq = step(t, view, pf, cfg, log, gate=gate)
            peak, mdd = max(peak, eq), max(mdd, 1 - eq / peak)
    sells = [x for x in log.trades if x["side"] == "SELL"]
    return {"return": eq / 1000 - 1, "max_dd": mdd, "trades": len(sells),
            "win_rate": (sum(x["pnl"] > 0 for x in sells) / len(sells)) if sells else 0.0}

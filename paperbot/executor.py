"""Executor: simulated fills with fees and slippage. Never touches a real exchange."""


class Portfolio:
    def __init__(self, cash, cfg):
        self.cash, self.cfg, self.positions = cash, cfg, {}

    def equity(self, prices):
        return self.cash + sum(p["qty"] * prices.get(pid, p["entry"]) for pid, p in self.positions.items())

    def buy(self, pid, ref_price, qty, stop, reason, t, ask=None):
        fill = (ask or ref_price) * (1 + self.cfg.slippage)
        cost = qty * fill
        fee = cost * self.cfg.taker_fee
        if qty <= 0 or cost + fee > self.cash or cost < 10:
            return None
        self.cash -= cost + fee
        self.positions[pid] = {"qty": qty, "entry": fill, "cost": cost + fee, "stop": stop,
                               "high": fill, "bars_held": 0, "t": t, "reason": reason}
        return {"t": t, "pair": pid, "side": "BUY", "qty": qty, "price": fill, "fee": fee,
                "slippage_pct": fill / ref_price - 1, "pnl": 0.0, "reason": reason}

    def sell(self, pid, ref_price, reason, t, bid=None):
        pos = self.positions.pop(pid)
        fill = (bid or ref_price) * (1 - self.cfg.slippage)
        proceeds = pos["qty"] * fill
        fee = proceeds * self.cfg.taker_fee
        self.cash += proceeds - fee
        pnl = proceeds - fee - pos["cost"]
        return {"t": t, "pair": pid, "side": "SELL", "qty": pos["qty"], "price": fill, "fee": fee,
                "slippage_pct": 1 - fill / ref_price, "pnl": pnl, "reason": reason}

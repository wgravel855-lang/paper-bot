"""One decision step, shared by the backtest and the live loop so both behave identically."""
from . import strategy, sizer, riskcheck


def step(t, history, portfolio, cfg, logger, quotes=None, gate=None, equity_on_close=True):
    """history: {pair: bars up to and including the latest closed bar}.
    quotes: optional {pair: {'bid','ask'}} for live spread-aware fills."""
    quotes = quotes or {}
    prices = {pid: bars[-1]["close"] for pid, bars in history.items() if bars}

    # exits first
    for pid in list(portfolio.positions):
        bars = history.get(pid)
        if not bars:
            continue
        go, reason, px = strategy.exit_signal(portfolio.positions[pid], bars, cfg)
        if go:
            tr = portfolio.sell(pid, px, reason, t, bid=quotes.get(pid, {}).get("bid"))
            eq = portfolio.equity(prices)
            logger.trade(tr, eq)
            if equity_on_close:
                logger.equity(t, eq)

    # entries
    for pid, bars in history.items():
        if pid in portfolio.positions or len(portfolio.positions) >= cfg.max_open_positions:
            continue
        go, reason, a = strategy.entry_signal(bars, cfg)
        if not go:
            continue
        q = quotes.get(pid)
        spread = (q["ask"] - q["bid"]) / q["ask"] if q else None
        ok, why = riskcheck.check(pid, bars, cfg, spread)
        if not ok:
            logger.activity(f"[rug-check] skipped {pid}: {why}")
            continue
        if gate is not None:
            ok, why = gate(pid, bars, t)
            if not ok:
                logger.activity(f"[gate] skipped {pid}: {why}")
                continue
            reason = f"{reason}; {why}"
        price = bars[-1]["close"]
        stop = price - cfg.stop_atr * a
        eq = portfolio.equity(prices)
        qty, note = sizer.size(eq, portfolio.cash, price, stop, cfg)
        tr = portfolio.buy(pid, price, qty, stop, f"{reason}; {note}", t, ask=q["ask"] if q else None)
        if tr:
            logger.trade(tr, portfolio.equity(prices))
    return portfolio.equity(prices)

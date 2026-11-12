"""Position sizer: size from current equity and stop distance, not a fixed ticket."""


def size(equity, cash, price, stop_price, cfg):
    risk_dollars = equity * cfg.risk_per_trade
    per_unit_risk = price - stop_price
    if per_unit_risk <= 0:
        return 0.0, "invalid stop"
    qty = risk_dollars / per_unit_risk
    cap = equity * cfg.max_position_pct / price
    qty = min(qty, cap, cash * 0.98 / (price * (1 + cfg.taker_fee + cfg.slippage)))
    note = (f"size: risk {cfg.risk_per_trade:.0%} of ${equity:,.2f} equity = ${risk_dollars:,.2f}, "
            f"stop {per_unit_risk / price:.1%} below entry")
    return max(qty, 0.0), note

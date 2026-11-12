# Paper Bot

A crypto trading bot that **only trades simulated money**. It reads real prices from
Coinbase's public API, but it never places a real order and needs no account or keys.

## The six parts
| Part | File | Job |
|---|---|---|
| Scanner | `paperbot/scanner.py` | Picks the 15 most-liquid USD pairs (stablecoins excluded) |
| Rug check | `paperbot/riskcheck.py` | Skips pairs that are too new, have wide spreads, or had a recent >25% candle |
| Sizer | `paperbot/sizer.py` | Risks 1% of current equity per trade, capped at 20% of equity per coin |
| Executor | `paperbot/executor.py` | Simulated fills with a 0.60% fee and 0.10% slippage, roughly Coinbase retail rates |
| Logger | `paperbot/logger.py` | Writes every trade and the reason for it to CSV |
| Dashboard | `paperbot/dashboard.py` | HTML page with the equity curve, stats, and trade log |

Strategy (`paperbot/strategy.py`): trend-following breakout. It buys when price closes above its
20-bar high while EMA20 > EMA50 and volume is at least 1.5x average. It sells on a 2.5-ATR trailing
stop, when EMA20 crosses below EMA50, or after 72 bars. All settings are in `paperbot/config.py`.

## Run it
```bash
pip install requests
python backtest.py --days 365          # replay the past year -> backtest_dashboard.html
python bot.py                          # live paper trading, runs until stopped -> index.html
python bot.py --reset                  # wipe the paper account and start over
```

## Honest results (backtests run 2026-11-12, $1,000 start)
| Version | Period | Result | BTC buy & hold | Trades | Win rate | Max drawdown |
|---|---|---|---|---|---|---|
| 1-hour candles | 120 days | **-44%** | +10% | 280 | 19% | 44% |
| 6-hour candles | 120 days | +29% | +10% | 49 | 31% | 8% |
| 6-hour candles | 1 year | +16% | -31% | 126 | 30% | 14% |

Caveats:
- **The 6-hour version's profit comes from a few big winners.** The top 3 trades made more than the
  whole year's net profit. Without them it loses money.
- **Survivorship bias:** the backtest trades today's top coins, which are the ones that survived.
  Real results would likely be worse.
- **6h was chosen after seeing that 1h lost money.** That is a small form of overfitting. Paper-trade
  for several weeks before believing any of these numbers.

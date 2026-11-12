# Paper Bot Lab

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

## Four accounts, side by side
| Account | How it decides |
|---|---|
| Fixed rules | The strategy above with fixed settings |
| Self-tuning | Every Sunday it re-tests 12 setting combos on the past year, then keeps the winner only if it also wins on the last 90 days it never saw |
| Buy the dip | Community-style mean reversion (`paperbot/strategy_dip.py`): buys a sharp drop (below the lower Bollinger band, RSI < 35) while the coin is above its 200-bar average; sells on the bounce back to the 20-bar average, a 2.5-ATR stop, or after 3 days |
| ML filter | Same buy signals, but a gradient-boosted model (scikit-learn) must approve each one. It predicts "price >1.5% higher in 24h" from 13 features (momentum, volume surge, volatility, Bitcoin trend, ...) |

Training (`train.py`) runs every Sunday via `.github/workflows/train.yml`:
- **Walk-forward test:** the last ~3 years are split into 90-day periods. Before each period every bot is
  trained or tuned using only earlier data, then trades it with fees. Results: `data/models/walkforward.json`.
- **ML data:** hourly candles from ~40 coins over ~4 years (every 3rd hour sampled), about 10x the original dataset.
  Prices are cached in `data/cache/` (and in the GitHub Actions cache), so later runs only download new candles.
The live **report card** checks every ML prediction against what actually happened 24 hours later.

## Run it
```bash
pip install -r requirements.txt
python train.py                        # tune + train (about 2 minutes)
python bot.py --once                   # one live paper cycle for all three accounts -> index.html
python backtest.py --days 365          # replay the fixed-rules bot on the past year
python bot.py --reset                  # wipe all paper accounts
```
On GitHub, `.github/workflows/paper-bot.yml` runs `bot.py --once` every hour.

## Honest notes
Walk-forward test (2026-11-12): 12 periods of 90 days, Nov 2023 – Nov 2026, each traded using only earlier data.

| Strategy | Avg per period | Periods up | Beat fixed rules | Worst period | All 12 chained |
|---|---|---|---|---|---|
| Fixed rules | +1.7% | 5 of 12 | — | -12.8% | +14% |
| Self-tuning | +4.3% | 5 of 12 | 7 of 12 | -9.1% | +54% |
| ML filter | +3.4% | 6 of 12 | 8 of 12 | -19.5% | +35% |
| Buy the dip | -1.0% | 2 of 12 | 8 of 12 | -3.5% | -11% |
| Just hold Bitcoin | +7.9% | 7 of 12 | — | -26.0% | +88% |

- **No bot beat simply holding Bitcoin over the 3 years.** The bots' advantage was smaller losses in bad periods.
- Self-tuning and the ML filter beat the fixed rules in most periods, but a big share of their gains came from the latest period.
- The model's accuracy (AUC) averaged 0.566 (0.5 = coin flip): a real but small edge.
- Coins are today's 15 most-traded (survivorship bias), so real results would likely be worse.
- Paper-trade for months before trusting any of this.

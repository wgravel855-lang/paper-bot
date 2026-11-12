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

## Three accounts, side by side
| Account | How it decides |
|---|---|
| Fixed rules | The strategy above with fixed settings |
| Self-tuning | Every Sunday it re-tests 12 setting combos on the past year, then keeps the winner only if it also wins on the last 90 days it never saw |
| ML filter | Same buy signals, but a gradient-boosted model (scikit-learn) must approve each one. It predicts "price >1.5% higher in 24h" from 13 features (momentum, volume surge, volatility, Bitcoin trend, ...) |

Training (`train.py`) runs every Sunday via `.github/workflows/train.yml`. Each run grades the tuned settings and
the model on the last 90 days, which they were not trained on, and saves the results to `data/models/`.
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
- First training run (2026-11-12): every setting combo **lost money** over the tuning year (-10% to -21%).
  On the last 90 days the fixed rules made +32%, the tuned settings +31% with smaller drops, and the ML filter +35%.
  That's one period, mostly a rising market, so it is not proof.
- The model's accuracy score (AUC) was 0.586, where 0.5 is a coin flip. Situations it approved hit the +1.5% target
  40% of the time vs 31% for all situations. That is a modest edge that fees can easily eat.
- The backtest uses today's most-liquid coins (survivorship bias), so real results would likely be worse.
- Paper-trade for months before trusting any of this.

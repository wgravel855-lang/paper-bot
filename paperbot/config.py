"""All tunable settings in one place. Edit these, not the code."""
from dataclasses import dataclass, field


@dataclass
class Config:
    # --- money (simulated) ---
    starting_cash: float = 1000.0

    # --- costs: be honest, these are roughly Coinbase retail rates ---
    taker_fee: float = 0.006          # 0.60% per fill
    slippage: float = 0.001           # 0.10% extra price impact per fill

    # --- scanner ---
    quote: str = "USD"
    granularity: int = 21600          # candle size in seconds (21600 = 6h; 1h lost money in testing)
    universe_size: int = 15           # trade only the N most-liquid pairs
    min_24h_usd_volume: float = 5_000_000

    # --- rug / safety check ---
    min_history_bars: int = 200       # pair must have this much price history
    max_spread_pct: float = 0.005     # skip if bid/ask spread > 0.5%
    max_bar_move_pct: float = 0.25    # skip if any recent candle moved > 25%
    stablecoins: tuple = ("USDT", "USDC", "DAI", "PYUSD", "EURC", "GUSD", "PAX", "FDUSD", "USDS")

    # --- strategy ---
    strategy: str = "breakout"        # "breakout" or "dip"
    # trend-following breakout settings
    ema_fast: int = 20
    ema_slow: int = 50
    breakout_lookback: int = 20       # close above the highest high of last N bars
    volume_spike: float = 1.5         # bar volume must be >= 1.5x its 20-bar average
    atr_period: int = 14
    stop_atr: float = 2.5             # trailing stop distance in ATRs
    max_hold_bars: int = 72           # time stop

    # --- sizer ---
    risk_per_trade: float = 0.01      # risk 1% of equity per trade (distance to stop)
    max_position_pct: float = 0.20    # never put more than 20% of equity in one coin
    max_open_positions: int = 4

    # --- live loop ---
    loop_seconds: int = 900           # check every 15 minutes
    data_dir: str = "data"

    excluded: list = field(default_factory=list)

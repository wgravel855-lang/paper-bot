"""Loads the trained model and acts as a gate on the strategy's buy signals.

The strategy decides on 6-hour candles; the model reads hourly features at the
exact hour that 6-hour candle closed."""
import json
import os
import pickle

from .features import frame, FEATURES

MODEL_DIR = "data/models"


class MLGate:
    def __init__(self, model_dir=MODEL_DIR, model=None, threshold=None, frames=None, gran=21600):
        self.model, self.threshold, self.gran = model, threshold, gran
        self.frames = frames            # {pair: precomputed hourly feature frame} for backtests
        self.btc = None                 # kept for compatibility with the simulator
        self.predictions = []
        self._btc_hourly = None
        if model is None and os.path.exists(os.path.join(model_dir, "model.pkl")):
            with open(os.path.join(model_dir, "model.pkl"), "rb") as f:
                self.model = pickle.load(f)
            with open(os.path.join(model_dir, "ml_report.json")) as f:
                self.threshold = json.load(f)["threshold"]

    @property
    def ready(self):
        return self.model is not None

    def _row(self, pid, decision_t):
        if self.frames is not None:
            fr = self.frames.get(pid)
        else:                            # live: fetch hourly candles on demand
            from . import data
            import time
            now = time.time()
            if self._btc_hourly is None:
                self._btc_hourly = [b for b in data.candles("BTC-USD", 3600, 900) if b["t"] + 3600 <= now]
            hourly = [b for b in data.candles(pid, 3600, 900) if b["t"] + 3600 <= now]
            fr = frame(hourly, self._btc_hourly) if hourly else None
        if fr is None:
            return None
        fr = fr.loc[:decision_t]
        if fr.empty or decision_t - fr.index[-1] > 3 * 3600:
            return None
        row = fr[FEATURES].iloc[[-1]]
        return None if row.isna().any(axis=None) else row

    def __call__(self, pid, bars, t):
        if not self.ready:
            return False, "ML: no model trained yet, skipping"
        decision_t = bars[-1]["t"] + self.gran - 3600    # the hourly candle that closes with this 6h candle
        row = self._row(pid, decision_t)
        if row is None:
            return False, "ML: not enough hourly data for this coin, skipping"
        p = float(self.model.predict_proba(row)[0, 1])
        ok = p >= self.threshold
        self.predictions.append({"bar_t": bars[-1]["t"], "pair": pid, "prob": p, "approved": ok,
                                 "close": bars[-1]["close"]})
        return ok, f"ML {'approved' if ok else 'rejected'}: {p:.0%} chance of +1.5% in 24h (needs {self.threshold:.0%})"

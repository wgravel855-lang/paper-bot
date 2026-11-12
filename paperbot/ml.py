"""Loads the trained model and acts as a gate on the baseline's buy signals."""
import json
import os
import pickle

from .features import frame, FEATURES

MODEL_DIR = "data/models"


class MLGate:
    def __init__(self, model_dir=MODEL_DIR, model=None, threshold=None):
        self.model, self.threshold = model, threshold
        if model is None and os.path.exists(os.path.join(model_dir, "model.pkl")):
            with open(os.path.join(model_dir, "model.pkl"), "rb") as f:
                self.model = pickle.load(f)
            with open(os.path.join(model_dir, "ml_report.json")) as f:
                self.threshold = json.load(f)["threshold"]
        self.btc = None
        self.predictions = []          # filled for the report card

    @property
    def ready(self):
        return self.model is not None

    def prob(self, bars, btc_bars):
        row = frame(bars[-120:], btc_bars[-150:])[FEATURES].iloc[[-1]]
        return float(self.model.predict_proba(row)[0, 1])

    def __call__(self, pid, bars, t):
        if not self.ready or self.btc is None:
            return False, "ML: no model trained yet, skipping"
        p = self.prob(bars, [b for b in self.btc if b["t"] <= bars[-1]["t"]])
        ok = p >= self.threshold
        self.predictions.append({"bar_t": bars[-1]["t"], "pair": pid, "prob": p, "approved": ok,
                                 "close": bars[-1]["close"]})
        verdict = "approved" if ok else "rejected"
        return ok, f"ML {verdict}: {p:.0%} chance of +1.5% in 24h (needs {self.threshold:.0%})"

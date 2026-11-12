"""The three paper accounts that run side by side."""
import json
import os

from .config import Config
from .ml import MLGate

TUNED_PATH = "data/models/tuned_params.json"

ACCOUNTS = {
    "baseline": "Fixed rules (original bot)",
    "tuned": "Self-tuning (re-picks its settings weekly)",
    "ml": "ML filter (model approves each trade)",
}


def make(name):
    cfg = Config()
    gate = None
    if name == "tuned" and os.path.exists(TUNED_PATH):
        with open(TUNED_PATH) as f:
            for k, v in json.load(f)["params"].items():
                setattr(cfg, k, v)
    if name == "ml":
        gate = MLGate()
    return cfg, gate

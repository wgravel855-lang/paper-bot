"""Weekly training. Run by GitHub Actions every Sunday (or by hand: python train.py).

1. Self-tuning: try 12 setting combinations on the year before the last 90 days,
   pick the best, then check it on the last 90 days (data it never saw).
   It is adopted only if it beats the default settings on that unseen data.
2. ML filter: train a gradient-boosted model to predict "price >1.5% higher in 24h"
   from 13 features. Train on everything before the last 90 days, grade it on
   the last 90 days, then refit on all data for live use.
"""
import itertools
import json
import os
import pickle
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from paperbot import data, scanner
from paperbot.config import Config
from paperbot.features import frame, label, FEATURES, NAMES
from paperbot.ml import MLGate
from paperbot.sim import simulate

OUT = "data/models"
VAL_DAYS, TUNE_DAYS, HISTORY_DAYS = 90, 365, 730
GRID = {"breakout_lookback": [10, 20, 40], "stop_atr": [2.0, 3.0], "volume_spike": [1.0, 1.5]}
TOP_PCT = 0.30   # the model approves only its most-confident 30% of situations


def score(r):
    return r["return"] - 0.5 * r["max_dd"]   # reward return, punish deep drawdowns


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    base = Config()
    universe = scanner.scan(base, log)
    if "BTC-USD" not in universe:
        universe.append("BTC-USD")
    bars_needed = HISTORY_DAYS * 86400 // base.granularity + base.min_history_bars
    hist = {}
    for pid in universe:
        b = data.candles(pid, base.granularity, bars_needed)
        if len(b) > base.min_history_bars + 100:
            hist[pid] = b
    log(f"[data] {len(hist)} pairs, up to {bars_needed} 6h candles each")

    t_end = max(b[-1]["t"] for b in hist.values())
    cutoff = t_end - VAL_DAYS * 86400
    tune_start = cutoff - TUNE_DAYS * 86400

    # ---------- 1. self-tuning ----------
    results = []
    for combo in itertools.product(*GRID.values()):
        params = dict(zip(GRID, combo))
        cfg = Config()
        for k, v in params.items():
            setattr(cfg, k, v)
        tr = simulate(hist, cfg, tune_start, cutoff)
        results.append((score(tr), params, tr))
        log(f"[tune] {params} -> train {tr['return']:+.1%} dd {tr['max_dd']:.0%} ({tr['trades']} trades)")
    results.sort(key=lambda r: r[0], reverse=True)
    best_params, best_train = results[0][1], results[0][2]
    default_params = {k: getattr(base, k) for k in GRID}
    best_val = simulate(hist, _cfg(best_params), cutoff, t_end)
    def_train = simulate(hist, base, tune_start, cutoff)
    def_val = simulate(hist, base, cutoff, t_end)
    dip_cfg = Config()
    dip_cfg.strategy = "dip"
    dip_train = simulate(hist, dip_cfg, tune_start, cutoff)
    dip_val = simulate(hist, dip_cfg, cutoff, t_end)
    log(f"[dip] tuning year {dip_train['return']:+.1%} ({dip_train['trades']} trades), "
        f"unseen 90d {dip_val['return']:+.1%} ({dip_val['trades']} trades)")
    adopted = score(best_val) >= score(def_val) and best_params != default_params
    tuned = {
        "trained_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "params": best_params if adopted else default_params,
        "adopted": adopted,
        "candidate": best_params,
        "candidate_train": best_train, "candidate_unseen": best_val,
        "default_train": def_train, "default_unseen": def_val,
        "verdict": (f"The picked combo beat the defaults on the last {VAL_DAYS} unseen days, scored as return minus half the biggest drop."
                    if adopted else
                    f"The best-looking combo did not beat the defaults on the last {VAL_DAYS} unseen days, so the defaults stay."
                    if best_params != default_params else "The defaults were already the best combination."),
        "grid_top5": [{"params": p, "train": r} for _, p, r in results[:5]],
    }
    _save("tuned_params.json", tuned)
    log(f"[tune] {tuned['verdict']}")

    # ---------- 2. ML filter ----------
    btc = hist["BTC-USD"]
    rows = []
    for pid, bars in hist.items():
        fr = frame(bars, btc)
        y, fwd = label(fr)
        fr["y"], fr["fwd"], fr["pair"] = y, fwd, pid
        rows.append(fr.iloc[60:])
    df = pd.concat(rows).dropna(subset=FEATURES + ["y"])
    embargo = 4 * base.granularity
    train = df[df.index < cutoff - embargo]
    test = df[df.index >= cutoff]
    log(f"[ml] {len(train)} training rows, {len(test)} unseen test rows")

    model = _model().fit(train[FEATURES], train["y"])
    p_train = model.predict_proba(train[FEATURES])[:, 1]
    thr = float(np.quantile(p_train, 1 - TOP_PCT))
    p_test = model.predict_proba(test[FEATURES])[:, 1]
    auc = float(roc_auc_score(test["y"], p_test))
    approved = p_test >= thr
    imp = permutation_importance(model, test[FEATURES], test["y"], scoring="roc_auc",
                                 n_repeats=3, random_state=0)
    importances = sorted(({"feature": f, "name": NAMES[f], "importance": float(m)}
                          for f, m in zip(FEATURES, imp.importances_mean)),
                         key=lambda d: d["importance"], reverse=True)
    gate = MLGate(model=model, threshold=thr)
    ml_val = simulate(hist, base, cutoff, t_end, gate=gate)
    log(f"[ml] unseen AUC {auc:.3f}; trading test: ML {ml_val['return']:+.1%} vs fixed rules {def_val['return']:+.1%}")

    # refit on everything for live use
    full = df[df.index < t_end - embargo]
    final = _model().fit(full[FEATURES], full["y"])
    final_thr = float(np.quantile(final.predict_proba(full[FEATURES])[:, 1], 1 - TOP_PCT))
    with open(os.path.join(OUT, "model.pkl"), "wb") as f:
        pickle.dump(final, f)
    report = {
        "trained_at": tuned["trained_at"],
        "threshold": final_thr,
        "target": "price more than 1.5% higher 24 hours later",
        "train_rows": int(len(full)),
        "unseen_days": VAL_DAYS,
        "unseen_auc": auc,
        "unseen_base_rate": float(test["y"].mean()),
        "unseen_hit_rate_approved": float(test["y"][approved].mean()) if approved.any() else None,
        "unseen_avg_24h_return_approved": float(test["fwd"][approved].mean()) if approved.any() else None,
        "unseen_avg_24h_return_all": float(test["fwd"].mean()),
        "trading_unseen_ml": ml_val, "trading_unseen_fixed": def_val,
        "trading_dip": {"tuning_year": dip_train, "unseen": dip_val},
        "importances": importances,
    }
    _save("ml_report.json", report)

    hpath = os.path.join(OUT, "training_history.json")
    hist_log = json.load(open(hpath)) if os.path.exists(hpath) else []
    hist_log.append({"date": tuned["trained_at"], "auc": auc, "tuned_adopted": adopted,
                     "unseen_fixed": def_val["return"], "unseen_tuned": best_val["return"],
                     "unseen_ml": ml_val["return"], "unseen_dip": dip_val["return"],
                     "year_fixed": def_train["return"], "year_dip": dip_train["return"]})
    _save("training_history.json", hist_log[-52:])
    log("[done] models written to data/models/")


def _cfg(params):
    cfg = Config()
    for k, v in params.items():
        setattr(cfg, k, v)
    return cfg


def _model():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200,
                                          min_samples_leaf=200, l2_regularization=1.0, random_state=0)


def _save(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1, default=float)


if __name__ == "__main__":
    main()

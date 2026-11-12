"""Weekly training + walk-forward test. Run by GitHub Actions every Sunday, or: python train.py

Walk-forward test: the last ~3 years are split into 90-day periods. For EACH period,
every bot is trained/tuned using ONLY data from before that period, then trades it.
That's the same thing that happens live, replayed many times, so luck averages out.

Then the live models are trained on all data:
  * Self-tuning: pick the best of 12 setting combos on the most recent year.
  * ML filter: gradient-boosted model on hourly features from ~40 coins, ~4 years,
    predicting "price >1.5% higher in 24h".
"""
import itertools
import json
import os
import pickle
import statistics
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from paperbot.config import Config
from paperbot.features import frame, label, FEATURES, NAMES, HORIZON_H
from paperbot.ml import MLGate
from paperbot.sim import simulate
from prefetch import fetch_all

OUT = "data/models"
PERIOD_DAYS, TUNE_DAYS, MAX_PERIODS = 90, 365, 12
GRID = {"breakout_lookback": [10, 20, 40], "stop_atr": [2.0, 3.0], "volume_spike": [1.0, 1.5]}
TOP_PCT = 0.30            # the model approves only its most-confident 30% of situations
NOT_CRYPTO = {"PAXG", "XAUT", "CBETH", "WBTC", "CBBTC", "STETH", "WSTETH"}  # gold / wrapped duplicates
DAY = 86400
EMBARGO = (HORIZON_H + 2) * 3600     # a training row's label must be fully known before the test starts
STRATS = ["fixed", "tuned", "ml", "dip"]


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def score(r):
    return r["return"] - 0.5 * r["max_dd"]


def cfg_with(**kw):
    c = Config()
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def tune(hist6, t0, t1):
    best = None
    for combo in itertools.product(*GRID.values()):
        params = dict(zip(GRID, combo))
        r = simulate(hist6, cfg_with(**params), t0, t1)
        if best is None or score(r) > score(best[1]):
            best = (params, r)
    return best


def model():
    return HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=250,
                                          min_samples_leaf=500, l2_regularization=1.0, random_state=0)


def fit(df):
    m = model().fit(df[FEATURES], df["y"])
    thr = float(np.quantile(m.predict_proba(df[FEATURES])[:, 1], 1 - TOP_PCT))
    return m, thr


def main():
    os.makedirs(OUT, exist_ok=True)
    t_start = time.time()
    ml_universe, h1, h6 = fetch_all(log)
    ml_universe = [p for p in ml_universe if p.split("-")[0] not in NOT_CRYPTO]
    trade = [p for p in ml_universe if p in h6 and len(h6[p]) > 400][:15]
    hist6 = {p: h6[p] for p in trade}
    btc1 = h1["BTC-USD"]

    # ---- build the ML dataset from hourly candles
    frames, parts = {}, []
    for pid in ml_universe:
        if len(h1.get(pid, [])) < 1000:
            continue
        fr = frame(h1[pid], btc1)
        if pid in hist6:
            frames[pid] = fr
        y, fwd = label(fr)
        d = fr[FEATURES].copy()
        d["y"], d["fwd"], d["pair"] = y, fwd, pid
        d = d.iloc[200:]
        parts.append(d[(d.index // 3600) % 3 == 2])     # every 3rd hour (incl. the live decision hours)
    df = pd.concat(parts).dropna(subset=FEATURES + ["y"]).sort_index()
    coins_used = int(df["pair"].nunique())
    log(f"[ml] dataset: {len(df):,} examples from {coins_used} coins")

    # ---- walk-forward periods
    t_end = max(b[-1]["t"] for b in hist6.values())
    btc6 = {b["t"]: b["close"] for b in hist6["BTC-USD"]}
    earliest = hist6["BTC-USD"][300]["t"] + TUNE_DAYS * DAY
    periods = []
    for k in range(MAX_PERIODS - 1, -1, -1):
        w1 = t_end - k * PERIOD_DAYS * DAY
        w0 = w1 - PERIOD_DAYS * DAY
        if w0 >= earliest:
            periods.append((w0, w1))
    log(f"[walk-forward] {len(periods)} periods of {PERIOD_DAYS} days")

    results, last_model = [], None
    for w0, w1 in periods:
        params, _ = tune(hist6, w0 - TUNE_DAYS * DAY, w0)
        r = {"start": time.strftime("%Y-%m-%d", time.gmtime(w0)), "end": time.strftime("%Y-%m-%d", time.gmtime(w1)),
             "fixed": simulate(hist6, Config(), w0, w1),
             "tuned": simulate(hist6, cfg_with(**params), w0, w1),
             "dip": simulate(hist6, cfg_with(strategy="dip"), w0, w1),
             "tuned_params": params}
        train_df = df[df.index < w0 - EMBARGO]
        m, thr = fit(train_df)
        r["ml"] = simulate(hist6, Config(), w0, w1, gate=MLGate(model=m, threshold=thr, frames=frames))
        test = df[(df.index >= w0) & (df.index < w1 - HORIZON_H * 3600)]
        p = m.predict_proba(test[FEATURES])[:, 1]
        r["auc"] = float(roc_auc_score(test["y"], p))
        r["base_rate"] = float(test["y"].mean())
        r["approved_hit"] = float(test["y"][p >= thr].mean()) if (p >= thr).any() else None
        b0 = btc6.get(w0) or next(v for t, v in sorted(btc6.items()) if t >= w0)
        r["btc"] = btc6[max(t for t in btc6 if t <= w1)] / b0 - 1
        results.append(r)
        last_model = (m, thr, test)
        log(f"[period {r['start']}] BTC {r['btc']:+.0%} | fixed {r['fixed']['return']:+.1%} tuned {r['tuned']['return']:+.1%} "
            f"ml {r['ml']['return']:+.1%} dip {r['dip']['return']:+.1%} | AUC {r['auc']:.3f}")

    summary = {}
    for s in STRATS + ["btc"]:
        rets = [r[s]["return"] if s != "btc" else r["btc"] for r in results]
        summary[s] = {"avg": statistics.mean(rets), "median": statistics.median(rets),
                      "positive": sum(x > 0 for x in rets), "worst": min(rets), "best": max(rets),
                      "compounded": float(np.prod([1 + x for x in rets]) - 1),
                      "beat_fixed": sum(r[s]["return"] > r["fixed"]["return"] for r in results) if s in STRATS else None,
                      "beat_btc": sum((r[s]["return"] if s != "btc" else r["btc"]) > r["btc"] for r in results)}
    summary["auc_avg"] = statistics.mean(r["auc"] for r in results)
    _save("walkforward.json", {"trained_at": _now(), "period_days": PERIOD_DAYS, "periods": results,
                               "summary": summary, "trade_coins": trade})

    # ---- live self-tuning settings: best combo on the most recent year
    params, rec = tune(hist6, t_end - TUNE_DAYS * DAY, t_end)
    wf = summary["tuned"]
    _save("tuned_params.json", {
        "trained_at": _now(), "params": params, "last_year": rec,
        "verdict": (f"In the walk-forward test this tuning method beat the fixed rules in {wf['beat_fixed']} of "
                    f"{len(results)} periods (average {wf['avg']:+.1%} vs {summary['fixed']['avg']:+.1%} per period)."),
    })

    # ---- live ML model: train on everything
    m_last, thr_last, test_last = last_model
    sample = test_last.sample(min(20000, len(test_last)), random_state=0)
    imp = permutation_importance(m_last, sample[FEATURES], sample["y"], scoring="roc_auc", n_repeats=3, random_state=0)
    importances = sorted(({"feature": f, "name": NAMES[f], "importance": float(v)}
                          for f, v in zip(FEATURES, imp.importances_mean)), key=lambda d: d["importance"], reverse=True)
    final_df = df[df.index < t_end + 21600 - EMBARGO]
    final, thr = fit(final_df)
    with open(os.path.join(OUT, "model.pkl"), "wb") as f:
        pickle.dump(final, f)
    last = results[-1]
    _save("ml_report.json", {
        "trained_at": _now(), "threshold": thr, "target": "price more than 1.5% higher 24 hours later",
        "train_rows": int(len(final_df)), "coins": coins_used, "unseen_days": PERIOD_DAYS,
        "unseen_auc": last["auc"], "unseen_base_rate": last["base_rate"],
        "unseen_hit_rate_approved": last["approved_hit"],
        "auc_avg_all_periods": summary["auc_avg"], "periods": len(results),
        "trading_unseen_ml": last["ml"], "trading_unseen_fixed": last["fixed"],
        "importances": importances,
    })

    hpath = os.path.join(OUT, "training_history.json")
    hist_log = json.load(open(hpath)) if os.path.exists(hpath) else []
    hist_log = [h for h in hist_log if "wf_avg_fixed" in h]          # drop old single-period format
    hist_log.append({"date": _now(), "auc": summary["auc_avg"], "periods": len(results),
                     **{f"wf_avg_{s}": summary[s]["avg"] for s in STRATS}})
    _save("training_history.json", hist_log[-52:])
    log(f"[done] {len(results)} periods, models written to {OUT}/ in {time.time() - t_start:.0f}s")


def _now():
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())


def _save(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1, default=float)


if __name__ == "__main__":
    main()

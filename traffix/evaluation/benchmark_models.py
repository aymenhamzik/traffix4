"""
Model benchmark: is HistGradientBoosting the right algorithm for each learned agent?

For every learning task, several algorithms are trained on the SAME data with the same
k-fold cross-validation (5 folds; 3 with --quick) and compared on:
  accuracy      F1 (classifiers) or MAE (regressors), mean +- std over folds
  train_s       training time per fold (seconds)
  predict_ms    time to predict ONE sample (what an agent pays every decision)
  size_kb       size of the saved model
The demand forecast is tested on a different YEAR (train 2025, test 2026) and also during
Ramadan 2026, against a "same date last year" baseline.
XGBoost and LightGBM are optional: skipped (and reported) if not installed.

  python scripts/benchmark.py models [--quick]
"""
import io
import os
import pickle
import random
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import f1_score, mean_absolute_error
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..core import config
from ..training.algorithms import algorithm_for

DATA = config.path("data", "training")
OUT = config.path("results", "benchmark")

# task: (csv, kind, rule) ; rule = the hand-written fallback each agent would otherwise use
TASKS = {
    "incident": ("incident", "clf", lambda X: (X[:, 0] >= 1).astype(int)),
    "sensor_health": ("sensor_health", "clf", lambda X: (X[:, 0] > 10).astype(int)),
    "pedestrian": ("pedestrian", "clf", lambda X: (X[:, 1] > 45).astype(int)),
    "ambulance_eta": ("ambulance_eta", "reg", lambda X: X[:, 0] / np.maximum(X[:, 1], 1.0)),
    "bus_eta": ("bus_eta", "reg", lambda X: X[:, 0] / np.maximum(X[:, 1], 2.0)),
    "bus_lateness": ("bus_lateness", "reg", lambda X: X[:, 0]),
    "edge_travel_time": ("edge_travel_time", "reg", lambda X: X[:, 3] / np.maximum(X[:, 2], 1.0)),
    "arrivals": ("arrivals", "reg", lambda X: X[:, 4]),
    "rain_speed": ("rain_speed", "reg", lambda X: 1 - 0.2 * X[:, 0]),
}


def algorithms(kind):
    """name -> factory. Optional libraries are skipped when missing."""
    algos = {}
    if kind == "clf":
        algos["linear"] = lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced"))
        algos["random_forest"] = lambda: RandomForestClassifier(n_estimators=150, max_depth=16, n_jobs=-1,
                                                                class_weight="balanced", random_state=0)
        algos["hist_gb"] = lambda: HistGradientBoostingClassifier(max_iter=200, class_weight="balanced", random_state=0)
        algos["mlp"] = lambda: make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300, early_stopping=True,
                                                                             random_state=0))
    else:
        algos["linear"] = lambda: make_pipeline(StandardScaler(), Ridge())
        algos["random_forest"] = lambda: RandomForestRegressor(n_estimators=150, max_depth=16, n_jobs=-1, random_state=0)
        algos["hist_gb"] = lambda: HistGradientBoostingRegressor(max_iter=200, random_state=0)
        algos["mlp"] = lambda: make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=300, early_stopping=True,
                                                                           random_state=0))
    try:
        import xgboost as xgb
        algos["xgboost"] = (lambda: xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, n_jobs=-1,
                                                     random_state=0, verbosity=0)) if kind == "clf" else \
                           (lambda: xgb.XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.1, n_jobs=-1,
                                                    random_state=0, verbosity=0))
    except ImportError:
        algos["xgboost"] = None
    try:
        import lightgbm as lgb
        algos["lightgbm"] = (lambda: lgb.LGBMClassifier(n_estimators=200, class_weight="balanced", random_state=0,
                                                       verbose=-1)) if kind == "clf" else \
                            (lambda: lgb.LGBMRegressor(n_estimators=200, random_state=0, verbose=-1))
    except ImportError:
        algos["lightgbm"] = None
    return algos


def _size_kb(model):
    buf = io.BytesIO()
    pickle.dump(model, buf)
    return round(len(buf.getvalue()) / 1024, 1)


def _predict_ms(model, X):
    rows = X[np.random.default_rng(0).integers(0, len(X), 100)]
    t = time.perf_counter()
    for r in rows:
        model.predict(r.reshape(1, -1))
    return round((time.perf_counter() - t) / len(rows) * 1000, 3)


def load_task(csv, kind, max_rows):
    p = os.path.join(DATA, f"{csv}.csv")
    if not os.path.exists(p):
        return None, None
    df = pd.read_csv(p).dropna()
    if kind == "clf":
        pos, neg = df[df.label == 1], df[df.label == 0]
        keep_neg = max(0, max_rows - len(pos))
        df = pd.concat([pos.sample(min(len(pos), max_rows // 2), random_state=0),
                        neg.sample(min(len(neg), keep_neg), random_state=0)])
        return df.drop(columns="label").values.astype(float), df["label"].values.astype(int)
    df = df.sample(min(len(df), max_rows), random_state=0)
    return df.iloc[:, :-1].values.astype(float), df.iloc[:, -1].values.astype(float)


def benchmark_task(name, csv, kind, rule, folds, max_rows):
    X, y = load_task(csv, kind, max_rows)
    if X is None or len(X) < 30 or (kind == "clf" and len(set(y)) < 2):
        return [{"task": name, "algorithm": "-", "note": "no training data: run python scripts/train.py first"}]
    split = (StratifiedKFold if kind == "clf" else KFold)(n_splits=folds, shuffle=True, random_state=0)
    rows = []
    # the rule needs no training
    scores = []
    for _, te in split.split(X, y):
        p = rule(X[te])
        scores.append(f1_score(y[te], p) if kind == "clf" else mean_absolute_error(y[te], p))
    rows.append({"task": name, "algorithm": "rule (fallback)", "metric": "F1" if kind == "clf" else "MAE",
                 "score": round(float(np.mean(scores)), 4), "std": round(float(np.std(scores)), 4),
                 "train_s": 0.0, "predict_ms": 0.0, "size_kb": 0.0, "rows": len(X)})
    for algo, factory in algorithms(kind).items():
        if factory is None:
            rows.append({"task": name, "algorithm": algo, "note": "not installed (pip install " + algo + ")"})
            continue
        scores, times = [], []
        model = None
        for tr, te in split.split(X, y):
            model = factory()
            t = time.perf_counter()
            model.fit(X[tr], y[tr])
            times.append(time.perf_counter() - t)
            p = model.predict(X[te])
            scores.append(f1_score(y[te], p) if kind == "clf" else mean_absolute_error(y[te], p))
        rows.append({"task": name, "algorithm": algo, "metric": "F1" if kind == "clf" else "MAE",
                     "score": round(float(np.mean(scores)), 4), "std": round(float(np.std(scores)), 4),
                     "train_s": round(float(np.mean(times)), 2), "predict_ms": _predict_ms(model, X),
                     "size_kb": _size_kb(model), "rows": len(X)})
        print(f"  {name:17s} {algo:16s} {rows[-1]['metric']} {rows[-1]['score']:.4f} ± {rows[-1]['std']:.4f}  "
              f"train {rows[-1]['train_s']:.2f}s  predict {rows[-1]['predict_ms']:.3f}ms", flush=True)
    return rows


def benchmark_forecast():
    """Train on 2025, test on 2026, overall and during Ramadan 2026."""
    from ..training.train_models import forecast_dataset
    rng = random.Random(0)
    Xtr, ytr, _, _ = forecast_dataset(2025, rng)
    Xte, yte, _, ram = forecast_dataset(2026, rng)
    key = lambda x: (int(x[2]), int(x[1]), int(x[0] * 2))
    sums = {}
    for x, v in zip(Xtr, ytr):
        sums.setdefault(key(x), []).append(v)
    avg = {k: float(np.mean(v)) for k, v in sums.items()}
    naive = np.array([avg.get(key(x), ytr.mean()) for x in Xte])
    rows = [{"task": "demand_forecast", "algorithm": "rule: same date last year", "metric": "MAE 2026",
             "score": round(mean_absolute_error(yte, naive), 4), "ramadan_mae": round(mean_absolute_error(yte[ram], naive[ram]), 4),
             "train_s": 0.0, "predict_ms": 0.0, "size_kb": 0.0, "rows": len(Xtr)}]
    for algo, factory in algorithms("reg").items():
        if factory is None:
            rows.append({"task": "demand_forecast", "algorithm": algo, "note": "not installed"})
            continue
        model = factory()
        t = time.perf_counter()
        model.fit(Xtr, ytr)
        tr = time.perf_counter() - t
        p = model.predict(Xte)
        rows.append({"task": "demand_forecast", "algorithm": algo, "metric": "MAE 2026",
                     "score": round(mean_absolute_error(yte, p), 4),
                     "ramadan_mae": round(mean_absolute_error(yte[ram], p[ram]), 4),
                     "train_s": round(tr, 2), "predict_ms": _predict_ms(model, Xte), "size_kb": _size_kb(model),
                     "rows": len(Xtr)})
        print(f"  demand_forecast   {algo:16s} MAE {rows[-1]['score']:.4f}  Ramadan {rows[-1]['ramadan_mae']:.4f}", flush=True)
    return rows


FIXED = {"demand_forecast": "hist_gb"}       # always trained with HistGradientBoosting (train_forecast)


def used_by_agent(task):
    """The algorithm the agent actually uses, from config/agents.yaml > model_algorithms."""
    return FIXED.get(task) or algorithm_for(task)


def _plain(name):
    return name.replace(" (ours)", "")


def best_of(df):
    """Per task: the best algorithm (excluding the rule), and where the agent's algorithm ranks."""
    df = df.assign(algorithm=df.algorithm.map(_plain))
    out = []
    for task, g in df[df.algorithm != "-"].dropna(subset=["score"]).groupby("task", sort=False):
        learned = g[~g.algorithm.str.startswith("rule")]
        if learned.empty:
            continue
        higher = learned.metric.iloc[0] == "F1"
        ranked = learned.sort_values("score", ascending=not higher).reset_index(drop=True)
        used = used_by_agent(task)
        ours = ranked.index[ranked.algorithm == used]
        out.append({"task": task, "metric": ranked.metric.iloc[0], "best": ranked.algorithm.iloc[0],
                    "best_score": ranked.score.iloc[0], "used_by_agent": used,
                    "used_rank": int(ours[0]) + 1 if len(ours) else None, "of": len(ranked),
                    "used_score": float(ranked.score[ours[0]]) if len(ours) else None,
                    "rule_score": float(g[g.algorithm.str.startswith("rule")].score.iloc[0])})
    return pd.DataFrame(out)


def chart(df, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tasks = [t for t in df.task.unique() if df[(df.task == t)].score.notna().any()]
    cols = 3
    rows = (len(tasks) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(16, 3.6 * rows))
    for ax, task in zip(np.ravel(axes), tasks):
        g = df[(df.task == task) & df.score.notna()].copy()
        g["algorithm"] = g.algorithm.map(_plain)
        used = used_by_agent(task)
        colors = ["#9e9e9e" if a.startswith("rule") else "#1f6f6b" if a == used else "#5c8ac9" for a in g.algorithm]
        labels = [f"{a}  (used)" if a == used else a for a in g.algorithm]
        ax.barh(labels, g.score, xerr=g.get("std"), color=colors)
        ax.set_title(f"{task} ({g.metric.iloc[0]}, {'higher' if g.metric.iloc[0] == 'F1' else 'lower'} is better)", fontsize=10)
        ax.invert_yaxis()
        ax.tick_params(labelsize=8)
    for ax in np.ravel(axes)[len(tasks):]:
        ax.axis("off")
    fig.suptitle("Model benchmark: each learned agent, same data, cross-validated. "
                 "Dark green = algorithm the agent uses (config/agents.yaml); grey = the rule it replaces")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=120)


def run(quick=False):
    os.makedirs(OUT, exist_ok=True)
    folds, max_rows = (3, 20000) if quick else (5, 60000)
    print(f"Model benchmark: {folds}-fold cross-validation, up to {max_rows} rows per task")
    rows = []
    for name, (csv, kind, rule) in TASKS.items():
        rows += benchmark_task(name, csv, kind, rule, folds, max_rows)
    rows += benchmark_forecast()
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "models.csv"), index=False)
    summary = best_of(df)
    summary.to_csv(os.path.join(OUT, "models_summary.csv"), index=False)
    chart(df, os.path.join(OUT, "models.png"))
    print("\nSummary (rank of the algorithm each agent uses, among learned algorithms):")
    print(summary.to_string(index=False))
    print(f"\nSaved {OUT}/models.csv, models_summary.csv, models.png")
    return df


def redraw():
    """Rebuild the summary and chart from results/benchmark/models.csv (no training)."""
    p = os.path.join(OUT, "models.csv")
    if not os.path.exists(p):
        print("No models.csv yet: run python scripts/benchmark.py models")
        return
    df = pd.read_csv(p)
    summary = best_of(df)
    summary.to_csv(os.path.join(OUT, "models_summary.csv"), index=False)
    chart(df, os.path.join(OUT, "models.png"))
    print(summary.to_string(index=False))

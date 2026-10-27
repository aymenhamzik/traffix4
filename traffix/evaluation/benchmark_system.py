"""
System benchmarks.

ABLATION  full TraffiX vs TraffiX with ONE network agent switched off, on several scenarios.
          The difference measures what each agent contributes (paired over seeds).
SWEEP     the morning peak at several demand levels (vehicles/h), for the baselines (fixed,
          Webster, actuated) and the three TraffiX traffic light agents: where does each break down?

  python scripts/benchmark.py ablation [--seeds 1 2] [--scenario ...]
  python scripts/benchmark.py sweep    [--seeds 1 2] [--levels 3000 4000 5000 5500]
"""
import os

import numpy as np
import pandas as pd
from scipy import stats

from ..core import config
from ..demand.generator import DemandGenerator
from .batch import run_jobs

OUT = config.path("results", "benchmark")
ABLATIONS = ["forecast", "weather", "incident", "rerouting", "emergency-route", "corridor", "transit-monitor"]
ABLATION_SCENARIOS = ["morning_peak", "evening_peak", "incident", "emergency", "rain", "combined"]
SWEEP_CONTROLLERS = ["fixed", "webster", "actuated", "traffix", "traffix_predictive", "traffix_rl"]
METRICS = {"veh_mean_wait_s": "car wait", "ped_mean_wait_s": "pedestrian wait",
           "ambulance_mean_travel_s": "emergency trip", "veh_unfinished": "unfinished trips",
           "clearance_truncations": "truncations"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


# ------------------------------------------------------------------ ablation
def ablation(seeds=(1, 2), scenarios=ABLATION_SCENARIOS, workers=1):
    route_dir = config.path("data", "generated")
    gen, sc = DemandGenerator(config.network_files()[0]), config.scenarios()
    for s in scenarios:
        for seed in seeds:
            if not os.path.exists(os.path.join(route_dir, f"{s}_seed{seed}.rou.xml")):
                gen.build(s, sc[s], seed, route_dir)
    controllers = ["traffix"] + [f"traffix-no-{a}" for a in ABLATIONS]
    jobs = [(c, s, seed, route_dir) for s in scenarios for c in controllers for seed in seeds]
    print(f"Ablation: {len(controllers)} variants x {len(scenarios)} scenarios x {len(seeds)} seeds")
    df = pd.DataFrame(run_jobs(jobs, os.path.join(OUT, "ablation.csv"), workers))
    return summarise_ablation(df)


def summarise_ablation(df):
    for c in METRICS:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    df["seed"] = df.seed.astype(int)
    full = df[df.controller == "traffix"].set_index(["scenario", "seed"])
    rows = []
    for variant, g in df[df.controller != "traffix"].groupby("controller"):
        g = g.set_index(["scenario", "seed"])
        both = g.index.intersection(full.index)
        if not len(both):
            continue
        row = {"agent switched off": variant.replace("traffix-no-", ""), "runs": len(both)}
        for col, label in METRICS.items():
            a, b = g.loc[both, col], full.loc[both, col]
            ok = a.notna() & b.notna()
            if not ok.any():
                continue
            change = (a[ok].mean() - b[ok].mean()) / max(abs(b[ok].mean()), 1e-9) * 100
            row[f"{label} change %"] = round(change, 1)
            if ok.sum() >= 2 and (a[ok] - b[ok]).std() > 0:
                row[f"{label} p"] = round(stats.ttest_rel(a[ok], b[ok]).pvalue, 4)
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "ablation_summary.csv"), index=False)
    per = df.pivot_table(index="scenario", columns="controller", values="veh_mean_wait_s").round(1)
    per.to_csv(os.path.join(OUT, "ablation_by_scenario.csv"))
    if len(out):
        ablation_chart(out, os.path.join(OUT, "ablation.png"))
    print("\nAblation (positive change = worse without the agent, so the agent helps):")
    print(out.to_string(index=False))
    return out


INFO_ONLY_NOTE = "information only: never changes a light"
CHART_METRICS = ["car wait", "pedestrian wait", "emergency trip", "unfinished trips"]   # truncations: too few to compare


def ablation_chart(out, path):
    """One panel per measure; bars faded when not significant (p >= 0.05), p-values printed,
    agents with no effect at all labelled as information-only."""
    plt = _plt()
    agents = list(out["agent switched off"])
    cols = [m for m in CHART_METRICS if f"{m} change %" in out]
    info_only = [a for a in agents
                 if all(abs(out.loc[out["agent switched off"] == a, f"{m} change %"].fillna(0).iloc[0]) < 1e-9 for m in cols)]
    fig, axes = plt.subplots(1, len(cols), figsize=(4.6 * len(cols), 0.55 * len(agents) + 2.6), sharey=True)
    for ax, m in zip(np.atleast_1d(axes), cols):
        vals = out[f"{m} change %"].fillna(0).values
        ps = out.get(f"{m} p", pd.Series([np.nan] * len(out))).values
        span = max(abs(vals).max(), 1.0)
        for i, (a, v, p) in enumerate(zip(agents, vals, ps)):
            if a in info_only:
                continue
            sig = isinstance(p, float) and not np.isnan(p) and p < 0.05
            ax.barh(i, v, color="#c0504d" if v > 0 else "#1f6f6b", alpha=1.0 if sig else 0.45,
                    edgecolor="#222" if sig else "none")
            label = f"{v:+.1f}%" + (f"  p={p:.2f}" if isinstance(p, float) and not np.isnan(p) else "")
            ax.text(v + (0.03 * span if v >= 0 else -0.03 * span), i, label, va="center",
                    ha="left" if v >= 0 else "right", fontsize=8, color="#222")
        for i, a in enumerate(agents):
            if a in info_only and m == cols[0]:
                ax.text(0.02 * span, i, INFO_ONLY_NOTE, va="center", fontsize=8, color="#777", style="italic")
        ax.axvline(0, color="#444", lw=1)
        ax.set_xlim(-span * 1.9, span * 1.9)
        ax.set_yticks(range(len(agents)))
        ax.set_yticklabels(agents)
        ax.invert_yaxis()
        ax.set_title(f"{m}\n% change when the agent is switched off", fontsize=10)
        ax.grid(axis="x", alpha=0.25)
    fig.suptitle("Ablation. Red: worse without the agent (it helps). Green: better without it (it costs). "
                 "Faded: not significant (p ≥ 0.05).", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, dpi=130)


def redraw():
    """Rebuild the ablation and sweep tables and charts from the saved CSVs (no simulation)."""
    done = False
    for name, fn in (("ablation.csv", summarise_ablation), ("sweep.csv", summarise_sweep)):
        p = os.path.join(OUT, name)
        if os.path.exists(p):
            fn(pd.read_csv(p))
            done = True
    if not done:
        print("No ablation.csv or sweep.csv in results/benchmark/ yet.")


# ------------------------------------------------------------------ demand sweep
def sweep(seeds=(1, 2), levels=(3000, 4000, 5000, 5500), controllers=SWEEP_CONTROLLERS, workers=1):
    route_dir = config.path("data", "generated", "sweep")
    base = config.simulation()["demand"]["base_vehicles_per_hour"]
    gen, scen = DemandGenerator(config.network_files()[0]), dict(config.scenarios()["morning_peak"])
    jobs = []
    for lvl in levels:
        name = f"demand_{lvl}"
        for seed in seeds:
            if not os.path.exists(os.path.join(route_dir, f"{name}_seed{seed}.rou.xml")):
                gen.build(name, {**scen, "demand_multiplier": lvl / base}, seed, route_dir)
        jobs += [(c, name, seed, route_dir) for c in controllers for seed in seeds]
    print(f"Demand sweep: {len(levels)} levels x {len(controllers)} controllers x {len(seeds)} seeds")
    df = pd.DataFrame(run_jobs(jobs, os.path.join(OUT, "sweep.csv"), workers))
    return summarise_sweep(df)


def summarise_sweep(df):
    df["level"] = df.scenario.str.replace("demand_", "").astype(int)
    for c in METRICS:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    table = df.groupby(["level", "controller"])[list(METRICS)].mean().round(1)
    table.to_csv(os.path.join(OUT, "sweep_summary.csv"))
    plt = _plt()
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    for ax, (col, label) in zip(axes, [("veh_mean_wait_s", "Car wait (s)"), ("ped_mean_wait_s", "Pedestrian wait (s)"),
                                       ("veh_unfinished", "Unfinished trips")]):
        for c, g in df.groupby("controller"):
            m = g.groupby("level")[col].mean()
            ax.plot(m.index, m.values, marker="o", label=c, lw=2.5 if c == "traffix" else 1.5)
        ax.set_xlabel("demand (vehicles/h at calendar factor 1)")
        ax.set_title(label)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.suptitle("Demand sweep, morning peak: where does each controller break down?")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(os.path.join(OUT, "sweep.png"), dpi=120)
    print("\nDemand sweep (mean over seeds):")
    print(table["veh_mean_wait_s"].unstack().to_string())
    return table

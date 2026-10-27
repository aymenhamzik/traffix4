"""
Benchmarks for the report. Each one resumes if interrupted; outputs go to results/benchmark/.

  python scripts/benchmark.py models   [--quick]        algorithms per learned agent (minutes)
  python scripts/benchmark.py ablation [--seeds 1 2]    one network agent switched off at a time
  python scripts/benchmark.py sweep    [--seeds 1 2]    demand levels, incl. the Webster baseline
  python scripts/benchmark.py synapse                   explainer questions in 3 languages
  python scripts/benchmark.py charts                    redraw all tables and charts from saved results (seconds)
  python scripts/benchmark.py all

Optional for the model benchmark:  python -m pip install xgboost lightgbm
"""
import argparse

import _path  # noqa: F401
from traffix.evaluation import benchmark_models, benchmark_synapse, benchmark_system

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("which", choices=["models", "ablation", "sweep", "synapse", "charts", "all"])
    p.add_argument("--quick", action="store_true", help="models: 3 folds, fewer rows")
    p.add_argument("--seeds", nargs="+", type=int, default=[1, 2])
    p.add_argument("--scenario", nargs="+", default=benchmark_system.ABLATION_SCENARIOS)
    p.add_argument("--levels", nargs="+", type=int, default=[3000, 4000, 5000, 5500])
    p.add_argument("--workers", type=int, default=1)
    a = p.parse_args()
    if a.which == "charts":
        benchmark_models.redraw()
        benchmark_system.redraw()
    if a.which in ("models", "all"):
        benchmark_models.run(a.quick)
    if a.which in ("synapse", "all"):
        benchmark_synapse.run()
    if a.which in ("ablation", "all"):
        benchmark_system.ablation(a.seeds, a.scenario, a.workers)
    if a.which in ("sweep", "all"):
        benchmark_system.sweep(a.seeds, a.levels, workers=a.workers)

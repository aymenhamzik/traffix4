"""Runs many simulations with resume: results saved after every run, finished runs skipped,
failures recorded (never raised). Shared by the experiments and the benchmarks."""
import csv
import os
import traceback
from multiprocessing import Pool


def _job(args):
    from .runner import run_one
    controller, scenario, seed, route_dir = args
    try:
        r = run_one(controller, scenario, seed, route_dir=route_dir, save_log=False)
        r["route_set"] = os.path.basename(route_dir)
        return r
    except Exception as e:
        return {"controller": controller, "scenario": scenario, "seed": seed,
                "error": f"{e.__class__.__name__}: {e}", "traceback": traceback.format_exc()[-1500:]}


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if not r.get("error")]


def save(rows, path):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def run_jobs(jobs, out, workers=1):
    """jobs: [(controller, scenario, seed, route_dir)]"""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = load(out)
    done = {(r["controller"], r["scenario"], int(r["seed"])) for r in rows}
    todo = [j for j in jobs if (j[0], j[1], j[2]) not in done]
    print(f"  {len(todo)} simulations to run ({len(done)} already saved in {os.path.basename(out)})", flush=True)
    results = map(_job, todo) if workers <= 1 else Pool(workers).imap(_job, todo)
    for r in results:
        if r.get("error"):
            print(f"  FAILED {r['controller']} {r['scenario']} seed {r['seed']}: {r['error']}", flush=True)
            with open(os.path.join(os.path.dirname(out), "failed_runs.log"), "a") as f:
                f.write(f"{r['controller']} {r['scenario']} seed {r['seed']}\n{r['traceback']}\n\n")
            continue
        rows.append(r)
        save(rows, out)
        print(f"  {r['scenario']:16s} {r['controller']:28s} seed {r['seed']}: car {float(r['veh_mean_wait_s']):6.1f}s "
              f"ped {float(r['ped_mean_wait_s']):5.1f}s unfinished {r['veh_unfinished']}", flush=True)
    return rows

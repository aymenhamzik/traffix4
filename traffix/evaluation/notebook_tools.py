"""
Helpers for the notebooks in notebooks/: run a SHORT version of a scenario with the real
system, keep the system's state afterwards (agents, message bus, decision log), and turn
log entries into plain sentences. Notebooks import the project; nothing is duplicated.
"""
import copy
import json
import os
from datetime import datetime

import pandas as pd
import sumolib

from ..core import config
from ..core.narrate import Narrator
from ..demand.generator import DemandGenerator
from ..simulation.network_model import load_models
from .runner import run_one

NB_ROUTES = config.path("data", "generated", "notebooks")


def _merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(out.get(k, {}), v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def build_short(scenario, minutes=10, seed=1, overrides=None):
    """A copy of a scenario that lasts `minutes`; returns its name. Built once, then reused."""
    sc = _merge(config.scenarios()[scenario], overrides)
    sc["duration"] = int(minutes * 60)
    name = f"nb_{scenario}_{minutes}m"
    if not os.path.exists(os.path.join(NB_ROUTES, f"{name}_seed{seed}.rou.xml")):
        DemandGenerator(config.network_files()[0]).build(name, sc, seed, NB_ROUTES)
    return name


def narrator_for(name, seed=1, route_dir=NB_ROUTES):
    meta = json.load(open(os.path.join(route_dir, f"{name}_seed{seed}.events.json")))
    net = config.network_files()[0]
    edges = {e.getID(): e.getName() for e in sumolib.net.readNet(net).getEdges() if not e.getFunction()}
    return Narrator({t: m.name for t, m in load_models(net).items()}, edges,
                    datetime.strptime(meta["start"], "%Y-%m-%d %H:%M"))


def short_run(scenario, controller="traffix", minutes=10, seed=1, overrides=None, every=0, capture=None):
    """Run a short scenario. capture(now, system) is called every `every` seconds; its results are
    returned in `snaps`. Returns (result dict, system after the run, snaps, narrator)."""
    name = build_short(scenario, minutes, seed, overrides)
    snaps, holder = [], {}

    def hook(now, system):
        holder["system"] = system
        if capture and every and int(now) % every == 0:
            snaps.append(capture(now, system))

    result = run_one(controller, name, seed, route_dir=NB_ROUTES, hooks=[hook], save_log=False)
    return result, holder.get("system"), snaps, narrator_for(name, seed)


def decisions(system, narrator, reasons=None, agent=None, lang="en", limit=None):
    """The decision log as a table of plain sentences, optionally filtered."""
    rows = []
    for e in system.log.entries:
        if reasons and not e["reason"].startswith(tuple(reasons)):
            continue
        if agent and not e["agent"].startswith(agent):
            continue
        rows.append({"id": e["id"], "time": narrator.clock(e["t"]), "agent": e["agent"], "reason": e["reason"],
                     "what happened": narrator.sentence(e, lang)})
    df = pd.DataFrame(rows)
    return df.tail(limit) if limit else df


def load_results(name="results.csv"):
    p = config.path("results", name)
    return pd.read_csv(p) if os.path.exists(p) else None


def load_benchmark(name):
    p = config.path("results", "benchmark", name)
    return pd.read_csv(p) if os.path.exists(p) else None

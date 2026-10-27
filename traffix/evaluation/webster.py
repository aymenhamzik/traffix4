"""
Webster baseline: the textbook way traffic engineers compute fixed-time plans
(F. V. Webster, Traffic Signal Settings, Road Research Technical Paper 39, 1958).

1. Calibrate: run the scenario once with SUMO's fixed plan and count vehicles per approach lane.
2. For each junction and phase: y = highest lane flow served / saturation flow (1,800 veh/h/lane);
   a lane served in several phases has its flow split between them.
3. Optimal cycle  C0 = (1.5 L + 5) / (1 - Y), L = lost time (5 s per phase), Y = sum of y,
   kept between 40 s and 120 s.
5. As in SUMO's own plans, the walk signal ends 5 s before each yellow (pedestrian clearance).
4. Greens shared in proportion to y, with minimums (12 s when a crossing walks, 7 s otherwise).
Plans are cached in results/benchmark/webster/ per scenario and seed.
"""
import json
import os

import sumo

from ..core import config
from ..simulation.backend import traci
from ..simulation.executor import Executor
from ..simulation.network_model import load_models

MIN_CYCLE = 40.0       # floor on Webster's cycle (60 s was tested and gave longer car waits here)
PED_CLEARANCE = 5      # s: walk signal ends this long before the yellow, as in SUMO's own plans
SAT_FLOW, LOST_PER_PHASE, YELLOW = 1800.0, 5.0, config.agents()["safety"]["yellow"]
SUMO_HOME = os.environ.get("SUMO_HOME", sumo.SUMO_HOME)
CACHE = config.path("results", "benchmark", "webster")


def calibrate(net, routes, seconds):
    """Vehicles per hour on every incoming lane of every junction, under SUMO's fixed plan."""
    models = load_models(net)
    lanes = sorted({l for m in models.values() for l in m.incoming_lanes})
    seen = {l: set() for l in lanes}
    stops = net.replace(".net.xml", ".stops.xml")
    traci.start([os.path.join(SUMO_HOME, "bin", "sumo"), "-n", net, "-r", routes, "--no-step-log", "true",
                 "--no-warnings", "true", "--ignore-route-errors", "true"] + (["-a", stops] if os.path.exists(stops) else []))
    try:
        while traci.simulation.getTime() < seconds and traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            for l in lanes:
                seen[l].update(traci.lane.getLastStepVehicleIDs(l))
    finally:
        traci.close()
    return {l: len(v) * 3600.0 / seconds for l, v in seen.items()}, models


def plan(models, flows):
    plans, info = {}, {}
    for tls, m in models.items():
        phases = m.green_phases
        # a lane served in several phases (e.g. through + left) has its flow split between them,
        # otherwise a short left-turn phase would be sized for the whole lane
        served = {}
        for k, ph in enumerate(phases):
            for l in m.vehicle_links:
                if ph[l.index] in "Gg":
                    served.setdefault(l.in_lane, set()).add(k)
        ys = []
        for k, ph in enumerate(phases):
            ys.append(max([flows.get(l, 0) / len(ks) / SAT_FLOW for l, ks in served.items() if k in ks] or [0.0]))
        Y = min(sum(ys), 0.9)
        L = LOST_PER_PHASE * len(phases)
        cycle = max(MIN_CYCLE, min(120.0, (1.5 * L + 5) / (1 - Y)))
        greens = []
        for ph, y in zip(phases, ys):
            walk = any(m.crossing_green(ph, c) for c in m.crossings)
            share = (cycle - L) * (y / sum(ys)) if sum(ys) > 0 else (cycle - L) / len(phases)
            greens.append(max(12.0 if walk else 7.0, round(share)))
        seq = []
        for i, (ph, g) in enumerate(zip(phases, greens)):
            nxt = phases[(i + 1) % len(phases)]
            walk_idx = [k for c in m.crossings if m.crossing_green(ph, c) for k in m.crossings[c]["indices"]]
            if walk_idx and g > PED_CLEARANCE + 5:
                cleared = "".join("r" if k in walk_idx else ch for k, ch in enumerate(ph))
                seq += [(ph, g - PED_CLEARANCE), (cleared, PED_CLEARANCE)]
            else:
                seq += [(ph, g)]
            seq += [(Executor._yellow(m, ph, nxt), YELLOW)]
        plans[tls] = seq
        info[tls] = {"cycle_s": round(sum(d for _, d in seq), 1), "greens_s": greens, "Y": round(Y, 3)}
    return plans, info


def plans_for(scenario, seed, route_dir):
    os.makedirs(CACHE, exist_ok=True)
    cache = os.path.join(CACHE, f"{os.path.basename(route_dir)}_{scenario}_{seed}.json")
    net = config.network_files()[0]
    if os.path.exists(cache):
        data = json.load(open(cache))
        return {t: [tuple(x) for x in p] for t, p in data["plans"].items()}, data["info"]
    meta = json.load(open(os.path.join(route_dir, f"{scenario}_seed{seed}.events.json")))
    flows, models = calibrate(net, os.path.join(route_dir, f"{scenario}_seed{seed}.rou.xml"),
                              min(1800, meta["duration"]))
    plans, info = plan(models, flows)
    json.dump({"plans": plans, "info": info}, open(cache, "w"), indent=1)
    return plans, info

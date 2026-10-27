"""
Synapse benchmark: does the explainer answer correctly, cite real entries, and abstain when it should?

30 questions (10 per language, config/benchmark_synapse.yaml) are asked against a fixed decision log
(the "combined" scenario, seed 1), with every available engine:
  template  built-in sentences (always)
  llm       the tool-using language-model agent (only if GROQ_API_KEY or ANTHROPIC_API_KEY is set)
Scores per engine and language:
  correct           answerable: not abstained AND cites at least one entry about the right vehicle/topic;
                    trick: abstained
  citation_valid    share of cited ids that exist in the log
  latency_ms        time to answer, excluding time spent waiting on the provider's rate limit
  python scripts/benchmark.py synapse
"""
import json
import os
import time
from datetime import datetime

import pandas as pd
import sumolib
import yaml

from ..agents.network.explainer import explain
from ..core import config
from ..core.decision_log import load
from ..core.narrate import Narrator
from ..simulation.network_model import load_models
from ..synapse import llm

OUT = config.path("results", "benchmark")
LOG = config.path("results", "logs", "decisions_traffix_combined_1.jsonl")


def fixed_log():
    route_dir = config.path("data", "generated")
    if not os.path.exists(LOG):
        from ..demand.generator import DemandGenerator
        from .runner import run_one
        if not os.path.exists(os.path.join(route_dir, "combined_seed1.rou.xml")):
            DemandGenerator(config.network_files()[0]).build("combined", config.scenarios()["combined"], 1, route_dir)
        print("  generating the reference log (combined scenario, seed 1)...", flush=True)
        run_one("traffix", "combined", 1)
    meta = json.load(open(os.path.join(route_dir, "combined_seed1.events.json")))
    net = config.network_files()[0]
    edges = {e.getID(): e.getName() for e in sumolib.net.readNet(net).getEdges() if not e.getFunction()}
    narrator = Narrator({t: m.name for t, m in load_models(net).items()}, edges,
                        datetime.strptime(meta["start"], "%Y-%m-%d %H:%M"))
    return load(LOG), narrator


def matches(entry, expect):
    if "vehicle" in expect:
        return entry["details"].get("vehicle") == expect["vehicle"]
    return entry["reason"].startswith(tuple(expect.get("reasons", [])))


def score(answer, expect, by_id):
    cites = answer.get("citations", [])
    valid = [c for c in cites if c in by_id]
    if expect.get("abstain"):
        ok = bool(answer.get("abstained"))
    else:
        ok = (not answer.get("abstained")) and any(matches(by_id[c], expect) for c in valid)
    return ok, (len(valid) / len(cites)) if cites else None


def run():
    os.makedirs(OUT, exist_ok=True)
    entries, narrator = fixed_log()
    by_id = {e["id"]: e for e in entries}
    questions = yaml.safe_load(open(config.path("config", "benchmark_synapse.yaml"), encoding="utf-8"))
    engines = ["template"] + (["agent"] if llm.available() else [])
    if not llm.available():
        print("  no GROQ_API_KEY / ANTHROPIC_API_KEY: benchmarking the template engine only")
    rows, errors = [], []
    for engine in engines:
        for q in questions:
            for lang in ("en", "fr", "ar"):
                t, waited0 = time.perf_counter(), llm.WAITED["s"]
                try:
                    a = explain(entries, q[lang], engine=engine, narrator=narrator, lang=lang)
                except Exception as e:
                    a = {"answer": f"ERROR {e}", "citations": [], "abstained": False}
                waited = llm.WAITED["s"] - waited0
                ms = (time.perf_counter() - t - waited) * 1000
                ok, valid = score(a, q["expect"], by_id)
                fell_back = engine == "agent" and a.get("engine") != "llm-agent"
                if fell_back:
                    ok = False                       # a template answer does not count for the LLM agent
                    if not errors:
                        print(f"  !! LLM agent fell back to templates: {a.get('llm_error', a.get('engine'))}", flush=True)
                    errors.append(a.get("llm_error", ""))
                rows.append({"engine": "llm agent" if engine == "agent" else "template", "lang": lang, "id": q["id"],
                             "answered_by": a.get("engine"), "fell_back": fell_back,
                             "tool_calls": len(a.get("tool_calls", [])),
                             "topic": q["topic"], "kind": "trick" if q["expect"].get("abstain") else "answerable",
                             "correct": ok, "abstained": bool(a.get("abstained")), "citations": len(a.get("citations", [])),
                             "citation_valid": valid, "latency_ms": round(ms, 1), "answer": a.get("answer", "")[:300]})
                print(f"  {rows[-1]['engine']:9s} {lang} Q{q['id']:2d} {'PASS' if ok else 'FAIL'} "
                      f"({rows[-1]['citations']} citations, {ms:.0f} ms"
                      + (f", +{waited:.0f} s rate-limit wait" if waited > 0.5 else "") + ")", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "synapse.csv"), index=False)
    summary = df.groupby(["engine", "lang"]).agg(
        accuracy=("correct", "mean"),
        answerable_correct=("correct", lambda s: s[df.loc[s.index, "kind"] == "answerable"].mean()),
        trick_abstained=("correct", lambda s: s[df.loc[s.index, "kind"] == "trick"].mean()),
        citation_validity=("citation_valid", "mean"), median_latency_ms=("latency_ms", "median"),
        fell_back_to_templates=("fell_back", "sum"), mean_tool_calls=("tool_calls", "mean")).round(3)
    summary.to_csv(os.path.join(OUT, "synapse_summary.csv"))
    if errors:
        print(f"\n  WARNING: the LLM agent fell back to templates {len(errors)} time(s): its rows count as failures."
              f"\n  Check the connection with: python scripts/check_llm.py")
    print("\nSynapse benchmark:")
    print(summary.to_string())
    return summary

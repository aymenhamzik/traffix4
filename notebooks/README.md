# Notebooks

Seven notebooks that walk through the project step by step. They **import** the real code in `traffix/`
(nothing is duplicated), run short simulations where needed, and read your saved results.

| Notebook | Shows | Needs | Run time |
|---|---|---|---|
| `01_simulation_and_data` | configuration, calendar (Ramadan, peaks), network, a scenario, training data | `scripts/train.py` for the data part | < 1 min |
| `02_junction_agents` | the 5 junction agents and the master inside a junction, an ambulance step by step | trained models | ~1 min |
| `03_network_agents` | the supermaster's agents in a scenario with rain, an incident and ambulances; alerts in 3 languages | trained models | ~1 min |
| `04_traffic_light_agents` | max-pressure vs predictive vs reinforcement learning, and why each switched | trained models | ~2 min |
| `05_models_and_training` | each model vs its rule, training a classifier and a regressor, the Ramadan 2026 forecast | training data and models | < 1 min |
| `06_results_and_benchmarks` | experiment tables, paired t-tests, emergency trips, ablation and sweep | `run_experiments.py`, benchmarks | seconds |
| `07_synapse` | sentences in 3 languages, questions, a trick question, the optional LLM agent | a decision log (made automatically) | 1-2 min |

## How to run

**In VS Code:** install the **Jupyter** extension, open a notebook, choose your Python as the kernel
(top right), then **Run All**.

**Or in the browser:**

    python -m pip install jupyter
    jupyter notebook notebooks

Run them from this folder (they find the project one level up). Sections whose results do not exist yet
say which command produces them instead of failing.

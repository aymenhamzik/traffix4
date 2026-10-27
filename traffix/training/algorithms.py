"""
Which algorithm each learned agent uses, chosen from the model benchmark
(config/agents.yaml > model_algorithms). Supported: hist_gb, xgboost, lightgbm.
If a library is not installed, training falls back to hist_gb and says so.
"""
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from ..core import config


def algorithm_for(task):
    choice = config.agents().get("model_algorithms", {})
    return choice.get(task, choice.get("default", "hist_gb"))


def make_model(task, kind, max_iter=200):
    """kind: 'clf' or 'reg'. Returns (model, algorithm actually used)."""
    algo = algorithm_for(task)
    if algo == "xgboost":
        try:
            import xgboost as xgb
            if kind == "clf":
                return xgb.XGBClassifier(n_estimators=max_iter, max_depth=6, learning_rate=0.1, n_jobs=-1,
                                         random_state=0, verbosity=0), "xgboost"
            return xgb.XGBRegressor(n_estimators=max_iter, max_depth=6, learning_rate=0.1, n_jobs=-1,
                                    random_state=0, verbosity=0), "xgboost"
        except ImportError:
            print(f"  [{task}] xgboost is not installed: using hist_gb (python -m pip install xgboost)")
    elif algo == "lightgbm":
        try:
            import lightgbm as lgb
            if kind == "clf":
                return lgb.LGBMClassifier(n_estimators=max_iter, class_weight="balanced", random_state=0,
                                          verbose=-1), "lightgbm"
            return lgb.LGBMRegressor(n_estimators=max_iter, random_state=0, verbose=-1), "lightgbm"
        except ImportError:
            print(f"  [{task}] lightgbm is not installed: using hist_gb (python -m pip install lightgbm)")
    if kind == "clf":
        return HistGradientBoostingClassifier(max_iter=max_iter, class_weight="balanced", random_state=0), "hist_gb"
    return HistGradientBoostingRegressor(max_iter=max_iter, random_state=0), "hist_gb"

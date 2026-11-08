"""Shared model loading and prediction utilities."""

from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd


FEATURES = (
    "estimated_hours",
    "priority",
    "workload_ratio",
    "required_skill_count",
    "task_complexity",
    "experience_years",
    "skill_match_ratio",
    "historical_performance",
)


def validate_prediction_inputs(values):
    errors = []
    numeric_limits = {
        "estimated_hours": (0.0, None),
        "workload_ratio": (0.0, None),
        "required_skill_count": (0.0, None),
        "task_complexity": (1.0, 5.0),
        "experience_years": (0.0, None),
        "skill_match_ratio": (0.0, 1.0),
        "historical_performance": (0.5, 1.5),
    }
    for field, (minimum, maximum) in numeric_limits.items():
        try:
            value = float(values[field])
        except (KeyError, TypeError, ValueError):
            errors.append(f"{field} must be numeric.")
            continue
        if value <= minimum and field in {"estimated_hours", "required_skill_count"}:
            errors.append(f"{field} must be greater than zero.")
        elif value < minimum:
            errors.append(f"{field} must be at least {minimum}.")
        if maximum is not None and value > maximum:
            errors.append(f"{field} must be at most {maximum}.")
    if values.get("priority") not in {"Low", "Medium", "High", "Critical"}:
        errors.append("priority must be Low, Medium, High, or Critical.")
    return errors


@lru_cache(maxsize=4)
def _load_model(path, modified_ns):
    return joblib.load(path)


def load_model(model_path):
    path = Path(model_path)
    if not path.exists():
        return None
    return _load_model(str(path), path.stat().st_mtime_ns)


def model_version(model_path):
    path = Path(model_path)
    if not path.exists():
        return None
    stat = path.stat()
    return f"{stat.st_size}-{stat.st_mtime_ns}"


def predict(model, values):
    errors = validate_prediction_inputs(values)
    if errors:
        raise ValueError(" ".join(errors))
    numeric_values = dict(values)
    numeric_values["priority"] = {
        "Low": 1,
        "Medium": 2,
        "High": 3,
        "Critical": 3,
    }[values["priority"]]
    frame = pd.DataFrame([{feature: numeric_values[feature] for feature in FEATURES}])
    return max(0.5, float(model.predict(frame)[0]))

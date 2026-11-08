"""Train and evaluate completion-time regression models."""

import json
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "training_data.csv"
MODEL_PATH = BASE_DIR / "models" / "completion_time_model.pkl"
RESULT_PATH = BASE_DIR / "models" / "model_evaluation.json"
FEATURES = ["estimated_hours", "priority", "workload_ratio", "required_skill_count", "task_complexity", "experience_years", "skill_match_ratio", "historical_performance"]
TARGET = "actual_hours"
RANDOM_STATE = 42
CV_FOLDS = 5


def load_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")
    data = pd.read_csv(DATA_PATH)
    missing = [column for column in FEATURES + [TARGET] if column not in data]
    if missing:
        raise ValueError(f"Missing dataset columns: {missing}")
    data = data[FEATURES + [TARGET]].apply(pd.to_numeric, errors="coerce")
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) <= CV_FOLDS:
        raise ValueError(f"At least {CV_FOLDS + 1} valid rows are required.")
    if (data[TARGET] < 0).any():
        raise ValueError(f"Target '{TARGET}' must be non-negative.")
    return data


def build_models():
    return {
        "Ridge Regression": Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=1.0))]),
        "Random Forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=RANDOM_STATE, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=3, loss="huber", random_state=RANDOM_STATE),
        "Extra Trees": ExtraTreesRegressor(n_estimators=300, min_samples_leaf=2, random_state=RANDOM_STATE, n_jobs=-1),
    }


def metrics(actual, predicted):
    return {"mae": float(mean_absolute_error(actual, predicted)), "rmse": float(mean_squared_error(actual, predicted) ** 0.5), "r2": float(r2_score(actual, predicted))}


def atomic_json_dump(payload, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as file:
        json.dump(payload, file, indent=2, allow_nan=False)
        file.write("\n")
        temporary = Path(file.name)
    temporary.replace(destination)


def train_models():
    print("\n====================================\n HUMAN-AWARE ML TRAINING SYSTEM\n====================================")
    data = load_data()
    X, y = data[FEATURES], data[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)
    folds = min(CV_FOLDS, len(X_train))
    cross_validation = KFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    candidates = {"Mean Baseline": DummyRegressor(strategy="mean"), **build_models()}
    results, best_name, best_cv_rmse = [], None, float("inf")
    print(f"\nUsable records: {len(data)}")
    print(f"Features: {len(FEATURES)} | CV folds: {folds}")
    print("\nMODEL COMPARISON\n------------------------------------")

    for name, model in candidates.items():
        scores = -cross_val_score(model, X_train, y_train, cv=cross_validation, scoring="neg_root_mean_squared_error", n_jobs=1)
        cv_rmse, cv_std = float(scores.mean()), float(scores.std())
        model.fit(X_train, y_train)
        test_metrics = metrics(y_test, model.predict(X_test))
        results.append({"model": name, "cv_rmse_mean": round(cv_rmse, 4), "cv_rmse_std": round(cv_std, 4), "test_mae": round(test_metrics["mae"], 4), "test_rmse": round(test_metrics["rmse"], 4), "test_r2": round(test_metrics["r2"], 4)})
        print(f"\n{name}: CV RMSE {cv_rmse:.4f} ± {cv_std:.4f} | test MAE {test_metrics['mae']:.4f} | test RMSE {test_metrics['rmse']:.4f} | R² {test_metrics['r2']:.4f}")
        if name != "Mean Baseline" and cv_rmse < best_cv_rmse:
            best_name, best_cv_rmse = name, cv_rmse

    best_model = build_models()[best_name]
    best_model.fit(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=MODEL_PATH.parent, delete=False) as file:
        temporary = Path(file.name)
    try:
        joblib.dump(best_model, temporary)
        temporary.replace(MODEL_PATH)
    finally:
        temporary.unlink(missing_ok=True)

    atomic_json_dump({"best_model": best_name, "selection_metric": "mean cross-validation RMSE on training split", "features": FEATURES, "target": TARGET, "total_records": int(len(data)), "training_records": int(len(X_train)), "testing_records": int(len(X_test)), "cross_validation_folds": folds, "random_state": RANDOM_STATE, "results": results}, RESULT_PATH)
    print("\n====================================\n TRAINING COMPLETED\n====================================")
    print(f"\nBest model: {best_name}\nModel saved: {MODEL_PATH}\nEvaluation saved: {RESULT_PATH}")


if __name__ == "__main__":
    train_models()

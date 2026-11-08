from pathlib import Path

from modules.modeling import load_model, predict

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "completion_time_model.pkl"


def predict_completion_time(
    estimated_hours,
    priority,
    workload_ratio,
    required_skill_count,
    task_complexity=3,
    experience_years=3,
    skill_match_ratio=0.8,
    historical_performance=1.0
):

    if not MODEL_PATH.exists():
        return None

    model = load_model(MODEL_PATH)
    if model is None:
        return None

    values = {
        "estimated_hours": estimated_hours,
        "priority": priority,
        "workload_ratio": workload_ratio,
        "required_skill_count": required_skill_count,
        "task_complexity": task_complexity,
        "experience_years": experience_years,
        "skill_match_ratio": skill_match_ratio,
        "historical_performance": historical_performance,
    }
    return round(predict(model, {**values, "priority": priority}), 2)

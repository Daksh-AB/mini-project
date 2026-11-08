import unittest
from pathlib import Path

from modules.modeling import predict, validate_prediction_inputs


class RecordingModel:
    def __init__(self):
        self.frame = None

    def predict(self, frame):
        self.frame = frame
        return [7.5]


class ModelingTests(unittest.TestCase):
    def test_prediction_validation_rejects_out_of_range_inputs(self):
        errors = validate_prediction_inputs({
            "estimated_hours": -1,
            "priority": "Urgent",
            "workload_ratio": 0,
            "required_skill_count": 1,
            "task_complexity": 3,
            "experience_years": 1,
            "skill_match_ratio": 1.2,
            "historical_performance": 1,
        })
        self.assertTrue(errors)
        self.assertTrue(any("estimated_hours" in error for error in errors))
        self.assertTrue(any("priority" in error for error in errors))

    def test_critical_priority_is_supported_by_model_features(self):
        model = RecordingModel()
        values = {
            "estimated_hours": 8,
            "priority": "Critical",
            "workload_ratio": 0.5,
            "required_skill_count": 2,
            "task_complexity": 3,
            "experience_years": 4,
            "skill_match_ratio": 1,
            "historical_performance": 1,
        }
        self.assertEqual(predict(model, values), 7.5)
        self.assertEqual(model.frame.iloc[0]["priority"], 3)


if __name__ == "__main__":
    unittest.main()

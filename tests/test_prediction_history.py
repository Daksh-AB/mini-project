import sqlite3
import unittest

from modules.prediction_history import get_prediction_records, record_prediction


class PredictionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE prediction_history (prediction_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "task_id INTEGER, employee_id INTEGER, model_version TEXT NOT NULL, "
            "predicted_hours REAL NOT NULL, input_json TEXT NOT NULL, created_at TEXT)"
        )
        self.connection.execute(
            "CREATE TABLE tasks (task_id INTEGER PRIMARY KEY, actual_hours REAL, estimated_hours REAL)"
        )
        self.connection.execute("INSERT INTO tasks VALUES (1, 9, 8)")
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def test_record_prediction_preserves_inputs_and_joined_actual_hours(self):
        record_prediction(
            1, 2, "model-version", 10.5, {"priority": "High"}, self.connection
        )
        row = get_prediction_records(self.connection)[0]
        self.assertEqual(row["model_version"], "model-version")
        self.assertEqual(row["predicted_hours"], 10.5)
        self.assertEqual(row["actual_hours"], 9)
        self.assertIn('"priority": "High"', row["input_json"])


if __name__ == "__main__":
    unittest.main()

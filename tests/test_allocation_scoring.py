import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import modules.allocation as allocation


class AllocationScoringTests(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parent / "_allocation_scoring.sqlite"
        self.db_path.unlink(missing_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE tasks (
                task_id INTEGER PRIMARY KEY,
                required_skills TEXT NOT NULL,
                estimated_hours REAL NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                skills TEXT NOT NULL,
                availability TEXT NOT NULL,
                max_capacity REAL NOT NULL,
                current_workload REAL NOT NULL,
                experience_years REAL NOT NULL,
                historical_performance REAL NOT NULL
            );
            INSERT INTO tasks VALUES (1, 'python', 8, 'Pending');
            INSERT INTO employees VALUES (1, 'Junior', 'python', 'Available', 40, 0, 1, 0.7);
            INSERT INTO employees VALUES (2, 'Senior', 'python', 'Available', 40, 0, 10, 1.3);
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.db_path.unlink(missing_ok=True)

    def test_recommendations_use_experience_and_performance(self):
        def connect():
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            return connection

        with patch.object(allocation, "get_connection", side_effect=connect):
            recommendations = allocation.get_recommendations(1)

        self.assertEqual(recommendations[0]["employee_id"], 2)
        self.assertGreater(
            recommendations[0]["total_score"], recommendations[1]["total_score"]
        )
        self.assertIn("experience_score", recommendations[0])
        self.assertIn("performance_score", recommendations[0])


if __name__ == "__main__":
    unittest.main()

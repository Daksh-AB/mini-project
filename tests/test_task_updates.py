import sqlite3
import unittest

from modules.extras import update_task_fields


class TaskUpdateValidationTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE tasks (task_id INTEGER PRIMARY KEY, title TEXT, description TEXT, "
            "required_skills TEXT, priority TEXT, estimated_hours REAL, task_complexity REAL)"
        )
        self.connection.execute(
            "INSERT INTO tasks VALUES (1, 'Build', '', 'python', 'Medium', 8, 3)"
        )
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def test_task_edit_rejects_invalid_hours(self):
        with self.assertRaisesRegex(ValueError, "Estimated hours"):
            update_task_fields(1, {"estimated_hours": 0}, self.connection)


if __name__ == "__main__":
    unittest.main()

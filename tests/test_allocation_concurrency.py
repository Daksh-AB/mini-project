import sqlite3
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import modules.allocation as allocation


class AllocationConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parent / "_allocation_concurrency.sqlite"
        self.db_path.unlink(missing_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE employees (
                employee_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                skills TEXT NOT NULL,
                availability TEXT NOT NULL,
                max_capacity REAL NOT NULL,
                current_workload REAL NOT NULL
            );
            CREATE TABLE tasks (
                task_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                required_skills TEXT NOT NULL,
                estimated_hours REAL NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE assignments (
                assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id),
                FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
            );
            INSERT INTO employees VALUES (1, 'Asha', 'python', 'Available', 10, 0);
            INSERT INTO tasks VALUES (1, 'One', 'python', 8, 'Pending');
            INSERT INTO tasks VALUES (2, 'Two', 'python', 8, 'Pending');
            """
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.db_path.unlink(missing_ok=True)

    def test_concurrent_assignments_cannot_both_consume_same_capacity(self):
        barrier = threading.Barrier(2)

        def connect():
            connection = sqlite3.connect(self.db_path, timeout=5)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection

        def assign(task_id):
            barrier.wait()
            return allocation.assign_task(task_id, 1)

        with patch.object(allocation, "get_connection", side_effect=connect):
            results = [None, None]
            threads = [
                threading.Thread(target=lambda: results.__setitem__(0, assign(1))),
                threading.Thread(target=lambda: results.__setitem__(1, assign(2))),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(sum(result[0] for result in results), 1)
        failed_result = next(result for result in results if not result[0])
        self.assertEqual(failed_result[1], "Insufficient employee capacity.")
        connection = sqlite3.connect(self.db_path)
        workload = connection.execute(
            "SELECT current_workload FROM employees WHERE employee_id = 1"
        ).fetchone()[0]
        assignments = connection.execute(
            "SELECT COUNT(*) FROM assignments WHERE status = 'Active'"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(workload, 8)
        self.assertEqual(assignments, 1)


if __name__ == "__main__":
    unittest.main()

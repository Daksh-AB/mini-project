import sqlite3
import unittest
from datetime import datetime

from modules.reports import build_report, period_bounds, report_csv_frames


class ReportTests(unittest.TestCase):
    def test_period_bounds_start_on_calendar_boundaries(self):
        now = datetime(2026, 11, 20, 15, 30)
        week_start, week_end = period_bounds("Weekly", now)
        month_start, month_end = period_bounds("Monthly", now)
        quarter_start, quarter_end = period_bounds("Quarterly", now)
        self.assertEqual(week_start, datetime(2026, 11, 16))
        self.assertEqual(week_end, datetime(2026, 11, 23))
        self.assertEqual(month_start, datetime(2026, 11, 1))
        self.assertEqual(month_end, datetime(2026, 12, 1))
        self.assertEqual(quarter_start, datetime(2026, 10, 1))
        self.assertEqual(quarter_end, datetime(2027, 1, 1))

    def test_report_filters_timestamped_events_and_exports_empty_sections(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript("""
            CREATE TABLE assignments (assignment_id INTEGER, task_id INTEGER,
                employee_id INTEGER, assigned_at TEXT, status TEXT);
            CREATE TABLE tasks (task_id INTEGER, title TEXT, priority TEXT,
                estimated_hours REAL, status TEXT, actual_hours REAL);
            CREATE TABLE employees (employee_id INTEGER, name TEXT,
                current_workload REAL, max_capacity REAL);
            CREATE TABLE reallocation_history (history_id INTEGER, task_id INTEGER,
                old_employee_id INTEGER, new_employee_id INTEGER, reason TEXT, changed_at TEXT);
            CREATE TABLE disturbances (disturbance_id INTEGER, disturbance_type TEXT,
                description TEXT, status TEXT, created_at TEXT);
            CREATE TABLE prediction_history (prediction_id INTEGER, task_id INTEGER,
                predicted_hours REAL, created_at TEXT);
        """)
        connection.execute("INSERT INTO employees VALUES (1, 'A', 10, 40)")
        connection.execute("INSERT INTO tasks VALUES (1, 'Task', 'High', 4, 'Pending', NULL)")
        connection.execute("INSERT INTO assignments VALUES (1, 1, 1, '2026-11-18 10:00:00', 'Active')")
        connection.execute("INSERT INTO assignments VALUES (2, 1, 1, '2026-10-01 10:00:00', 'Active')")
        connection.commit()
        report = build_report(connection, "Weekly", datetime(2026, 11, 20, 15, 30))
        self.assertEqual(report["summary"]["assignments"], 1)
        self.assertEqual(len(report["reallocations"]), 0)
        frames = report_csv_frames(report)
        self.assertEqual(list(frames["summary"].columns)[0], "assignments")
        self.assertIn("assignments", frames)
        connection.close()


if __name__ == "__main__":
    unittest.main()

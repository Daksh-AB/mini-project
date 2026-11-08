import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(__file__).resolve().parent / "_test_database.sqlite"

    def tearDown(self):
        self.db_path.unlink(missing_ok=True)

    def test_connections_enable_foreign_keys(self):
        with patch.object(database, "DB_PATH", self.db_path):
            connection = database.get_connection()
            try:
                self.assertEqual(
                    connection.execute("PRAGMA foreign_keys").fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_init_db_runs_extra_schema_migrations(self):
        with patch.object(database, "DB_PATH", self.db_path):
            database.init_db()
            connection = sqlite3.connect(self.db_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            finally:
                connection.close()

        self.assertTrue({"users", "audit_log", "task_dependencies"} <= tables)

    def test_init_db_records_schema_version(self):
        with patch.object(database, "DB_PATH", self.db_path):
            database.init_db()
            connection = sqlite3.connect(self.db_path)
            try:
                version = connection.execute(
                    "SELECT version FROM schema_meta WHERE id = 1"
                ).fetchone()[0]
            finally:
                connection.close()
        self.assertEqual(version, database.SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()

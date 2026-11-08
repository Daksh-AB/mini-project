import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.backup_database import backup_database


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).resolve().parent / "_backup_source.sqlite"
        self.destination = Path(__file__).resolve().parent / "_backup_copy.sqlite"
        for path in (self.source, self.destination):
            path.unlink(missing_ok=True)
        connection = sqlite3.connect(self.source)
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES ('safe')")
        connection.commit()
        connection.close()

    def tearDown(self):
        for path in (self.source, self.destination):
            path.unlink(missing_ok=True)

    def test_backup_contains_source_data(self):
        backup_database(self.source, self.destination)
        connection = sqlite3.connect(self.destination)
        value = connection.execute("SELECT value FROM marker").fetchone()[0]
        connection.close()
        self.assertEqual(value, "safe")

    def test_backup_script_runs_directly_from_project_root(self):
        destination = Path(__file__).resolve().parent / "_backup_cli.sqlite"
        destination.unlink(missing_ok=True)
        try:
            result = subprocess.run(
                [sys.executable, "scripts/backup_database.py", str(destination)],
                capture_output=True,
                text=True,
                cwd=Path(__file__).resolve().parent.parent,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(destination.exists())
        finally:
            destination.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

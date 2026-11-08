import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

import modules.health as health


class HealthTests(unittest.TestCase):
    def test_health_reports_database_and_model_state(self):
        connection = sqlite3.connect(":memory:")
        with patch.object(health, "get_connection", return_value=connection):
            result = health.check_health(Path("missing-model.pkl"))
        connection.close()
        self.assertFalse(result["model"])
        self.assertTrue(result["database"])
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()

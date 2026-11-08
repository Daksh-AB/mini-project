import os
import sqlite3
import unittest
from unittest.mock import patch

from modules.auth import authenticate_user, initialize_auth
from modules.extras import create_user, delete_user, list_users


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, "
            "role TEXT NOT NULL, must_change INTEGER NOT NULL DEFAULT 0, created_at TEXT)"
        )

    def tearDown(self):
        self.connection.close()

    def test_initialize_auth_creates_hashed_default_user(self):
        with patch.dict(os.environ, {
            "TASK_APP_USERNAME": "manager",
            "TASK_APP_PASSWORD": "a-secure-password",
        }):
            initialize_auth(self.connection)

        row = self.connection.execute(
            "SELECT username, password_hash, role, must_change FROM users"
        ).fetchone()
        self.assertEqual(row["username"], "manager")
        self.assertNotEqual(row["password_hash"], "a-secure-password")
        self.assertEqual(row["role"], "manager")
        self.assertEqual(row["must_change"], 0)

    def test_authenticate_user_rejects_bad_password(self):
        self.connection.execute(
            "INSERT INTO users (username, password_hash, role, must_change) VALUES (?, ?, ?, ?)",
            ("manager", "pbkdf2$200000$00112233445566778899aabbccddeeff$bad", "manager", 0),
        )
        self.assertIsNone(
            authenticate_user("manager", "wrong-password", self.connection)
        )

    def test_authenticate_user_returns_role_and_password_state(self):
        with patch.dict(os.environ, {
            "TASK_APP_USERNAME": "manager",
            "TASK_APP_PASSWORD": "a-secure-password",
        }):
            initialize_auth(self.connection)

        identity = authenticate_user(
            " MANAGER ", "a-secure-password", self.connection
        )
        self.assertEqual(identity["username"], "manager")
        self.assertEqual(identity["role"], "manager")
        self.assertFalse(identity["must_change"])

    def test_manager_can_create_and_delete_viewer_account(self):
        with patch.dict(os.environ, {
            "TASK_APP_USERNAME": "manager",
            "TASK_APP_PASSWORD": "a-secure-password",
        }):
            initialize_auth(self.connection)
        created, _ = create_user(
            "viewer", "viewer-password", "viewer", self.connection
        )
        self.assertTrue(created)
        self.assertEqual(len(list_users(self.connection)), 2)
        deleted, _ = delete_user("viewer", self.connection)
        self.assertTrue(deleted)
        self.assertEqual(len(list_users(self.connection)), 1)

    def test_default_user_initialization_is_idempotent(self):
        with patch.dict(os.environ, {
            "TASK_APP_USERNAME": "manager",
            "TASK_APP_PASSWORD": "a-secure-password",
        }):
            initialize_auth(self.connection)
            initialize_auth(self.connection)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            1,
        )

    def test_reset_password_secret_updates_existing_account(self):
        with patch.dict(os.environ, {
            "TASK_APP_USERNAME": "manager",
            "TASK_APP_PASSWORD": "old-password",
            "TASK_APP_RESET_PASSWORD": "new-password",
        }):
            initialize_auth(self.connection)
        self.assertIsNotNone(
            authenticate_user("manager", "new-password", self.connection)
        )
        self.assertIsNone(
            authenticate_user("manager", "old-password", self.connection)
        )


if __name__ == "__main__":
    unittest.main()

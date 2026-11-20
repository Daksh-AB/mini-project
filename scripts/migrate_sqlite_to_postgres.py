"""Copy the existing SQLite application database into PostgreSQL.

Usage:
    $env:DATABASE_URL = "<private Neon URL>"
    python scripts/migrate_sqlite_to_postgres.py
"""

import os
import sqlite3
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from database import DB_PATH, init_db  # noqa: E402


TABLES = (
    "employees", "tasks", "assignments", "reallocation_history",
    "disturbances", "schema_meta", "prediction_history",
    "task_dependencies", "audit_log", "users", "skill_levels",
)
IDENTITY_COLUMNS = {
    "employees": "employee_id", "tasks": "task_id", "assignments": "assignment_id",
    "reallocation_history": "history_id", "disturbances": "disturbance_id",
    "prediction_history": "prediction_id", "audit_log": "log_id",
}


def migrate(source_path=DB_PATH):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set DATABASE_URL to the private Neon connection string first.")
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("Install requirements.txt before running the migration.") from error

    init_db()
    source = sqlite3.connect(source_path)
    try:
        with psycopg.connect(database_url) as target:
            with target.cursor() as cursor:
                for table in TABLES:
                    source_columns = [
                        row[1] for row in source.execute(f"PRAGMA table_info({table})")
                    ]
                    if not source_columns:
                        continue
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = %s",
                        (table,),
                    )
                    target_columns = {row[0] for row in cursor.fetchall()}
                    columns = [column for column in source_columns if column in target_columns]
                    if not columns:
                        continue
                    placeholders = ", ".join(["%s"] * len(columns))
                    quoted = ", ".join(f'"{column}"' for column in columns)
                    cursor.execute(f'DELETE FROM "{table}"')
                    rows = source.execute(
                        f'SELECT {quoted} FROM "{table}"'
                    ).fetchall()
                    if rows:
                        cursor.executemany(
                            f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
                            rows,
                        )
                    identity = IDENTITY_COLUMNS.get(table)
                    if identity:
                        cursor.execute(
                            "SELECT pg_get_serial_sequence(%s, %s)",
                            (table, identity),
                        )
                        sequence = cursor.fetchone()[0]
                        if sequence:
                            cursor.execute(
                                f"SELECT setval(%s, COALESCE(MAX(\"{identity}\"), 1), true) FROM \"{table}\"",
                                (sequence,),
                            )
                    print(f"{table}: copied {len(rows)} rows")
    finally:
        source.close()


if __name__ == "__main__":
    migrate()

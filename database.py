import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "task_allocation.db"
SCHEMA_VERSION = 2


def get_connection():
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def add_column_if_missing(cursor, table, column, definition):
    cursor.execute(f"PRAGMA table_info({table})")
    existing_columns = [row["name"] for row in cursor.fetchall()]

    if column not in existing_columns:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def init_db():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            skills TEXT NOT NULL,
            availability TEXT DEFAULT 'Available',
            max_capacity REAL DEFAULT 40,
            current_workload REAL DEFAULT 0,
            experience_years REAL DEFAULT 0,
            historical_performance REAL DEFAULT 1.0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            required_skills TEXT NOT NULL,
            priority TEXT DEFAULT 'Medium',
            estimated_hours REAL DEFAULT 1,
            status TEXT DEFAULT 'Pending',
            task_complexity REAL DEFAULT 3
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (task_id) REFERENCES tasks(task_id),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reallocation_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            old_employee_id INTEGER,
            new_employee_id INTEGER,
            reason TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS disturbances (
            disturbance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            disturbance_type TEXT NOT NULL,
            employee_id INTEGER,
            task_id INTEGER,
            description TEXT,
            status TEXT DEFAULT 'Detected',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute(
        """
        INSERT INTO schema_meta (id, version) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET
            version = excluded.version,
            updated_at = CURRENT_TIMESTAMP
        """,
        (SCHEMA_VERSION,),
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction_history (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            employee_id INTEGER,
            model_version TEXT NOT NULL,
            predicted_hours REAL NOT NULL,
            input_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(task_id),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
        )
    """)

    # Safely upgrade existing databases.
    add_column_if_missing(
        cursor, "employees", "experience_years",
        "REAL DEFAULT 0"
    )

    add_column_if_missing(
        cursor, "employees", "historical_performance",
        "REAL DEFAULT 1.0"
    )

    add_column_if_missing(
        cursor, "tasks", "task_complexity",
        "REAL DEFAULT 3"
    )

    connection.commit()
    connection.close()

    # Keep additive tables and optional columns in the same startup migration
    # path as the core schema. The import is local to avoid an import cycle.
    from modules.extras import ensure_schema
    ensure_schema()

    print("Database and tables created/updated successfully!")


if __name__ == "__main__":
    init_db()

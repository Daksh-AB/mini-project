import sqlite3
import os
from pathlib import Path


class _CompatRow(dict):
    """Mapping row that also supports SQLite-style numeric indexing."""
    def __init__(self, values, columns):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class _PostgresCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        sql = sql.replace("?", "%s").replace("BEGIN IMMEDIATE", "BEGIN")
        self._cursor.execute(sql, params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._row(row)

    def fetchall(self):
        return [self._row(row) for row in self._cursor.fetchall()]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def _row(self, row):
        if row is None:
            return None
        columns = [column.name for column in self._cursor.description]
        return _CompatRow(row, columns)


class _PostgresConnection:
    is_postgres = True

    def __init__(self, connection):
        self._connection = connection
        self.row_factory = None

    def execute(self, sql, params=()):
        cursor = _PostgresCursor(self._connection.cursor())
        return cursor.execute(sql, params)

    def cursor(self):
        return _PostgresCursor(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "task_allocation.db"
SCHEMA_VERSION = 2


def get_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError(
                "DATABASE_URL is set, but psycopg is not installed. "
                "Install dependencies from requirements.txt."
            ) from error
        return _PostgresConnection(psycopg.connect(database_url))

    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def get_database_path():
    """Return the local or deployment-mounted SQLite path."""
    configured_directory = os.getenv("TASK_APP_DATA_DIR")
    if configured_directory:
        return Path(configured_directory) / "task_allocation.db"
    return DB_PATH


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
    if getattr(connection, "is_postgres", False):
        _init_postgres(connection, cursor)
        connection.close()
        from modules.extras import ensure_schema
        ensure_schema()
        print("Database and tables created/updated successfully!")
        return

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


def _init_postgres(connection, cursor):
    """Create the core schema using PostgreSQL-compatible identity columns."""
    statements = [
        """CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL, skills TEXT NOT NULL,
            availability TEXT DEFAULT 'Available', max_capacity DOUBLE PRECISION DEFAULT 40,
            current_workload DOUBLE PRECISION DEFAULT 0, experience_years DOUBLE PRECISION DEFAULT 0,
            historical_performance DOUBLE PRECISION DEFAULT 1.0)""",
        """CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            title TEXT NOT NULL, description TEXT, required_skills TEXT NOT NULL,
            priority TEXT DEFAULT 'Medium', estimated_hours DOUBLE PRECISION DEFAULT 1,
            status TEXT DEFAULT 'Pending', task_complexity DOUBLE PRECISION DEFAULT 3)""",
        """CREATE TABLE IF NOT EXISTS assignments (
            assignment_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES tasks(task_id), employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'Active')""",
        """CREATE TABLE IF NOT EXISTS reallocation_history (
            history_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            task_id INTEGER NOT NULL REFERENCES tasks(task_id), old_employee_id INTEGER,
            new_employee_id INTEGER, reason TEXT, changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS disturbances (
            disturbance_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            disturbance_type TEXT NOT NULL, employee_id INTEGER, task_id INTEGER,
            description TEXT, status TEXT DEFAULT 'Detected', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS schema_meta (
            id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS prediction_history (
            prediction_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            task_id INTEGER, employee_id INTEGER, model_version TEXT NOT NULL,
            predicted_hours DOUBLE PRECISION NOT NULL, input_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
    ]
    for statement in statements:
        cursor.execute(statement)
    cursor.execute(
        """INSERT INTO schema_meta (id, version) VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET version = EXCLUDED.version,
        updated_at = CURRENT_TIMESTAMP""", (1, SCHEMA_VERSION)
    )
    connection.commit()


if __name__ == "__main__":
    init_db()

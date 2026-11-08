"""Runtime health checks used by the application and deployment probes."""

from pathlib import Path

from database import get_connection


def check_health(model_path):
    checks = {"database": False, "model": Path(model_path).exists()}
    connection = None
    try:
        connection = get_connection()
        connection.execute("SELECT 1").fetchone()
        checks["database"] = True
    except Exception:
        checks["database"] = False
    finally:
        if connection is not None:
            connection.close()
    checks["ready"] = all(checks.values())
    return checks

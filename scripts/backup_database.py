"""Create a consistent SQLite backup without stopping the application."""

import argparse
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import DB_PATH


def backup_database(source=DB_PATH, destination=None):
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Database not found: {source}")
    if destination is None:
        destination = source.parent / "backups" / (
            f"{source.stem}_{datetime.now():%Y%m%d_%H%M%S}.db"
        )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
        destination_connection.commit()
    finally:
        destination_connection.close()
        source_connection.close()
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Back up the task database")
    parser.add_argument("destination", nargs="?", help="Optional backup path")
    args = parser.parse_args()
    print(backup_database(destination=args.destination))

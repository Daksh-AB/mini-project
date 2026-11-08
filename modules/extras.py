"""Extra features for the Human-Aware Task Allocation app.

Everything here is additive: it only creates new tables, adds two optional
columns to ``tasks`` (due_date, actual_hours) and never changes the behaviour
of the existing modules.

All functions accept an optional ``conn`` (sqlite3 connection) so they can be
unit-tested against an in-memory database. When ``conn`` is omitted the app's
own ``database.get_connection`` is used.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import os
import random
import re
import secrets
import sqlite3
import statistics
from contextlib import contextmanager
from datetime import date, datetime

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

DEFAULT_USERNAME = "manager"
DEFAULT_PASSWORD = "manager123"
ROLES = ("manager", "viewer")
PBKDF2_ITERATIONS = 200_000
MIN_PASSWORD_LENGTH = 8

SCORE_WEIGHTS = {
    "skill": 0.40,
    "workload": 0.30,
    "experience": 0.15,
    "performance": 0.15,
}

PRIORITY_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

EDITABLE_TASK_FIELDS = {
    "title",
    "description",
    "required_skills",
    "priority",
    "estimated_hours",
    "task_complexity",
    "due_date",
    "actual_hours",
}

STRATEGY_LABELS = {
    "random": "Random",
    "round_robin": "Round-robin",
    "human_aware": "Human-aware",
}


# ------------------------------------------------------------------
# Database plumbing
# ------------------------------------------------------------------

@contextmanager
def _db(conn=None):
    owned = conn is None
    if owned:
        from database import get_connection  # imported lazily for testability
        conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        if owned:
            conn.close()


def _columns(db, table):
    return [row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()]


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def ensure_schema(conn=None):
    """Create the extra tables and optional task columns (safe to re-run)."""
    with _db(conn) as db:
        task_columns = _columns(db, "tasks")
        if task_columns:
            if "due_date" not in task_columns:
                db.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
            if "actual_hours" not in task_columns:
                db.execute("ALTER TABLE tasks ADD COLUMN actual_hours REAL")

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS task_dependencies (
                task_id INTEGER NOT NULL,
                depends_on INTEGER NOT NULL,
                PRIMARY KEY (task_id, depends_on)
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                logged_at TEXT NOT NULL,
                username TEXT,
                action TEXT NOT NULL,
                details TEXT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                must_change INTEGER NOT NULL DEFAULT 0,
                created_at TEXT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_levels (
                employee_id INTEGER NOT NULL,
                skill TEXT NOT NULL,
                level INTEGER NOT NULL,
                PRIMARY KEY (employee_id, skill)
            )
            """
        )


# ------------------------------------------------------------------
# Users, passwords and roles
# ------------------------------------------------------------------

def hash_password(password, salt=None, iterations=PBKDF2_ITERATIONS):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        scheme, iterations, salt_hex, hash_hex = str(stored).split("$")
        if scheme != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            str(password).encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def ensure_default_user(conn=None):
    """Seed the first manager account (only when no users exist yet)."""
    with _db(conn) as db:
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count:
            return
        username = _configured_value("TASK_APP_USERNAME", DEFAULT_USERNAME)
        password = _configured_value("TASK_APP_PASSWORD", DEFAULT_PASSWORD)
        db.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, must_change, created_at) "
            "VALUES (?, ?, 'manager', ?, ?)",
            (
                username,
                hash_password(password),
                1 if password == DEFAULT_PASSWORD else 0,
                _now(),
            ),
        )


def _configured_value(name, default):
    """Read deployment configuration from env vars or Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except Exception:
        return default


def authenticate(username, password, conn=None):
    """Return {'username', 'role', 'must_change'} or None."""
    with _db(conn) as db:
        row = db.execute(
            "SELECT username, password_hash, role, must_change FROM users "
            "WHERE lower(username) = lower(?)",
            (str(username).strip(),),
        ).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return {
                "username": row["username"],
                "role": row["role"],
                "must_change": bool(row["must_change"]),
            }
    return None


def validate_new_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password == DEFAULT_PASSWORD:
        return "Please choose a password different from the default one."
    return None


def create_user(username, password, role, conn=None):
    username = str(username).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,32}", username):
        return False, "Username must be 3-32 characters (letters, numbers, . _ -)."
    if role not in ROLES:
        return False, "Role must be manager or viewer."
    problem = validate_new_password(password)
    if problem:
        return False, problem
    with _db(conn) as db:
        exists = db.execute(
            "SELECT 1 FROM users WHERE lower(username) = lower(?)", (username,)
        ).fetchone()
        if exists:
            return False, "That username already exists."
        db.execute(
            "INSERT INTO users (username, password_hash, role, must_change, created_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (username, hash_password(password), role, _now()),
        )
    return True, f"User '{username}' created."


def change_password(username, new_password, conn=None):
    problem = validate_new_password(new_password)
    if problem:
        return False, problem
    with _db(conn) as db:
        cursor = db.execute(
            "UPDATE users SET password_hash = ?, must_change = 0 WHERE username = ?",
            (hash_password(new_password), username),
        )
        if cursor.rowcount == 0:
            return False, "User not found."
    return True, "Password updated."


def list_users(conn=None):
    with _db(conn) as db:
        rows = db.execute(
            "SELECT username, role, must_change, created_at FROM users ORDER BY username"
        ).fetchall()
        return [dict(row) for row in rows]


def delete_user(username, conn=None):
    with _db(conn) as db:
        row = db.execute(
            "SELECT role FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            return False, "User not found."
        if row["role"] == "manager":
            managers = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'manager'"
            ).fetchone()[0]
            if managers <= 1:
                return False, "You cannot delete the last manager account."
        db.execute("DELETE FROM users WHERE username = ?", (username,))
    return True, f"User '{username}' deleted."


# ------------------------------------------------------------------
# Audit log
# ------------------------------------------------------------------

def log_action(username, action, details="", conn=None):
    with _db(conn) as db:
        db.execute(
            "INSERT INTO audit_log (logged_at, username, action, details) VALUES (?, ?, ?, ?)",
            (_now(), username or "system", action, details),
        )


def get_audit_log(limit=1000, conn=None):
    with _db(conn) as db:
        rows = db.execute(
            "SELECT log_id, logged_at, username, action, details "
            "FROM audit_log ORDER BY log_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


# ------------------------------------------------------------------
# Task extras: due dates, actual hours, editing
# ------------------------------------------------------------------

def update_task_fields(task_id, fields, conn=None):
    """Update only columns that exist and are allowed. Returns True if updated."""
    with _db(conn) as db:
        existing = set(_columns(db, "tasks"))
        usable = {
            key: value
            for key, value in fields.items()
            if key in EDITABLE_TASK_FIELDS and key in existing
        }
        if not usable:
            return False

        if {"title", "required_skills", "priority", "estimated_hours", "task_complexity"} & usable.keys():
            current = db.execute(
                "SELECT title, required_skills, priority, estimated_hours, task_complexity "
                "FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if not current:
                return False
            from modules.validation import validate_task
            proposed = {
                "title": usable.get("title", current["title"]),
                "required_skills": usable.get("required_skills", current["required_skills"]),
                "priority": usable.get("priority", current["priority"]),
                "estimated_hours": usable.get("estimated_hours", current["estimated_hours"]),
                "task_complexity": usable.get("task_complexity", current["task_complexity"]),
            }
            errors = validate_task(**proposed)
            if errors:
                raise ValueError(" ".join(errors))
        assignments = ", ".join(f"{key} = ?" for key in usable)
        db.execute(
            f"UPDATE tasks SET {assignments} WHERE task_id = ?",
            (*usable.values(), task_id),
        )
        return True


def last_task_id(conn=None):
    with _db(conn) as db:
        row = db.execute("SELECT MAX(task_id) FROM tasks").fetchone()
        return row[0]


def get_task_extras(conn=None):
    """Return {task_id: {'due_date': date|None, 'actual_hours': float|None}}."""
    with _db(conn) as db:
        columns = set(_columns(db, "tasks"))
        if not {"due_date", "actual_hours"} <= columns:
            return {}
        rows = db.execute(
            "SELECT task_id, due_date, actual_hours FROM tasks"
        ).fetchall()
        return {
            row["task_id"]: {
                "due_date": _parse_date(row["due_date"]),
                "actual_hours": row["actual_hours"],
            }
            for row in rows
        }


# ------------------------------------------------------------------
# Task dependencies
# ------------------------------------------------------------------

def get_dependencies(conn=None):
    """Return a list of (task_id, depends_on) pairs."""
    with _db(conn) as db:
        rows = db.execute(
            "SELECT task_id, depends_on FROM task_dependencies ORDER BY task_id, depends_on"
        ).fetchall()
        return [(row["task_id"], row["depends_on"]) for row in rows]


def would_create_cycle(dependencies, task_id, depends_on):
    """True if making task_id depend on depends_on would create a loop."""
    if task_id == depends_on:
        return True
    graph = {}
    for child, parent in dependencies:
        graph.setdefault(child, set()).add(parent)
    stack = [depends_on]
    seen = set()
    while stack:
        node = stack.pop()
        if node == task_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.get(node, ()))
    return False


def add_dependency(task_id, depends_on, conn=None):
    with _db(conn) as db:
        rows = db.execute("SELECT task_id, depends_on FROM task_dependencies").fetchall()
        existing = [(row[0], row[1]) for row in rows]
        if (task_id, depends_on) in existing:
            return False, "That dependency already exists."
        if would_create_cycle(existing, task_id, depends_on):
            return False, "That dependency would create a loop (or a task depending on itself)."
        db.execute(
            "INSERT INTO task_dependencies (task_id, depends_on) VALUES (?, ?)",
            (task_id, depends_on),
        )
    return True, "Dependency added."


def remove_dependency(task_id, depends_on, conn=None):
    with _db(conn) as db:
        db.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? AND depends_on = ?",
            (task_id, depends_on),
        )


def remove_task_links(task_id, conn=None):
    """Remove every dependency that mentions a (deleted) task."""
    with _db(conn) as db:
        db.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? OR depends_on = ?",
            (task_id, task_id),
        )


def blocking_tasks(task_id, dependencies, status_by_id):
    """IDs of dependencies of task_id that are not Completed yet."""
    return [
        parent
        for child, parent in dependencies
        if child == task_id and status_by_id.get(parent) != "Completed"
    ]


# ------------------------------------------------------------------
# Skills and skill proficiency
# ------------------------------------------------------------------

def parse_skills(value):
    if isinstance(value, (set, frozenset, list, tuple)):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return {part.strip().lower() for part in str(value or "").split(",") if part.strip()}


def skill_match_ratio(employee_skills, required_skills):
    required = parse_skills(required_skills)
    if not required:
        return 0.0
    return len(parse_skills(employee_skills) & required) / len(required)


def set_skill_levels(employee_id, levels, conn=None):
    with _db(conn) as db:
        for skill, level in levels.items():
            db.execute(
                "INSERT INTO skill_levels (employee_id, skill, level) VALUES (?, ?, ?) "
                "ON CONFLICT(employee_id, skill) DO UPDATE SET level = excluded.level",
                (employee_id, str(skill).strip().lower(), int(level)),
            )


def get_skill_levels(employee_id, conn=None):
    with _db(conn) as db:
        rows = db.execute(
            "SELECT skill, level FROM skill_levels WHERE employee_id = ?", (employee_id,)
        ).fetchall()
        return {row["skill"]: row["level"] for row in rows}


def get_all_skill_levels(conn=None):
    with _db(conn) as db:
        rows = db.execute("SELECT employee_id, skill, level FROM skill_levels").fetchall()
    result = {}
    for row in rows:
        result.setdefault(row["employee_id"], {})[row["skill"]] = row["level"]
    return result


# ------------------------------------------------------------------
# Scoring, explanation and what-if helpers (pure functions)
# ------------------------------------------------------------------

def utilization_pct(current, capacity):
    capacity = float(capacity or 0)
    return (float(current or 0) / capacity * 100) if capacity > 0 else 0.0


def utilization_after(current, capacity, delta_hours):
    return utilization_pct(float(current or 0) + float(delta_hours or 0), capacity)


def score_breakdown(employee, task, levels=None):
    """Explainable 0-100 suitability score split into four factors.

    skill       - share of required skills the employee has (weighted by
                  proficiency levels when they are available)
    workload    - remaining capacity (headroom)
    experience  - years of experience, capped at 10
    performance - historical performance factor mapped from 0.5-1.5 to 0-100
    """
    required = parse_skills(task.get("required_skills"))
    matched = parse_skills(employee.get("skills")) & required
    ratio = len(matched) / len(required) if required else 0.0

    skill_points = ratio * 100
    if matched and levels:
        proficiency = statistics.mean(levels.get(skill, 3) / 5 for skill in matched)
        skill_points = ratio * (0.6 + 0.4 * proficiency) * 100

    capacity = float(employee.get("max_capacity") or 0)
    current = float(employee.get("current_workload") or 0)
    headroom = max(0.0, min(1.0, (capacity - current) / capacity)) if capacity > 0 else 0.0

    experience = min(float(employee.get("experience_years") or 0) / 10, 1.0)
    performance = max(
        0.0, min(1.0, float(employee.get("historical_performance") or 1.0) - 0.5)
    )

    components = {
        "skill": skill_points,
        "workload": headroom * 100,
        "experience": experience * 100,
        "performance": performance * 100,
    }
    weighted = {key: components[key] * SCORE_WEIGHTS[key] for key in components}
    return {
        "components": components,
        "weighted": weighted,
        "total": round(sum(weighted.values()), 1),
        "skill_match_ratio": ratio,
        "eligible": employee.get("availability") == "Available" and ratio > 0,
    }


def prediction_features(task, employee):
    """Build the keyword arguments expected by predict_completion_time()."""
    required = parse_skills(task.get("required_skills"))
    priority = task.get("priority") or "Medium"
    capacity = float(employee.get("max_capacity") or 0)
    current = float(employee.get("current_workload") or 0)
    return {
        "estimated_hours": float(task.get("estimated_hours") or 0),
        "priority": "High" if priority == "Critical" else priority,
        "workload_ratio": current / capacity if capacity > 0 else 0.0,
        "required_skill_count": len(required),
        "task_complexity": float(task.get("task_complexity") or 3.0),
        "experience_years": float(employee.get("experience_years") or 0),
        "skill_match_ratio": skill_match_ratio(employee.get("skills"), required),
        "historical_performance": float(employee.get("historical_performance") or 1.0),
    }


def prediction_accuracy(records):
    """records: dicts with 'actual', 'predicted' and 'estimate' hours."""
    if not records:
        return None
    model_errors = [abs(r["predicted"] - r["actual"]) for r in records]
    estimate_errors = [abs(r["estimate"] - r["actual"]) for r in records]
    model_mae = statistics.mean(model_errors)
    estimate_mae = statistics.mean(estimate_errors)
    improvement = (
        (estimate_mae - model_mae) / estimate_mae * 100 if estimate_mae > 0 else 0.0
    )
    return {
        "count": len(records),
        "model_mae": model_mae,
        "estimate_mae": estimate_mae,
        "improvement_pct": improvement,
    }


# ------------------------------------------------------------------
# Alerts
# ------------------------------------------------------------------

def detect_alerts(employees, tasks, extras, dependencies, today=None):
    """Find overloads, overdue / due-soon tasks and blocked work in progress."""
    today = today or date.today()
    status_by_id = {task["task_id"]: task["status"] for task in tasks}
    alerts = []

    for employee in employees:
        capacity = float(employee.get("max_capacity") or 0)
        current = float(employee.get("current_workload") or 0)
        if capacity <= 0:
            continue
        utilization = current / capacity * 100
        if utilization > 100:
            alerts.append({
                "type": "overload", "severity": "high",
                "ref_type": "employee", "ref_id": employee["employee_id"],
                "message": f"{employee['name']} is over capacity at {utilization:.0f}% ({current:g}/{capacity:g} h).",
            })
        elif utilization >= 90:
            alerts.append({
                "type": "overload", "severity": "medium",
                "ref_type": "employee", "ref_id": employee["employee_id"],
                "message": f"{employee['name']} is close to capacity at {utilization:.0f}% ({current:g}/{capacity:g} h).",
            })

    for task in tasks:
        if task["status"] == "Completed":
            continue
        due = (extras.get(task["task_id"]) or {}).get("due_date")
        if due:
            days = (due - today).days
            if days < 0:
                alerts.append({
                    "type": "overdue", "severity": "high",
                    "ref_type": "task", "ref_id": task["task_id"],
                    "message": f"'{task['title']}' is {-days} day(s) past its due date ({due:%d %b %Y}).",
                })
            elif days <= 3:
                alerts.append({
                    "type": "due_soon", "severity": "medium",
                    "ref_type": "task", "ref_id": task["task_id"],
                    "message": f"'{task['title']}' is due in {days} day(s) ({due:%d %b %Y}).",
                })
        blockers = blocking_tasks(task["task_id"], dependencies, status_by_id)
        if blockers and task["status"] == "In Progress":
            alerts.append({
                "type": "blocked", "severity": "medium",
                "ref_type": "task", "ref_id": task["task_id"],
                "message": f"'{task['title']}' is in progress but depends on unfinished task(s): "
                           f"{', '.join(str(b) for b in blockers)}.",
            })

    order = {"high": 0, "medium": 1}
    alerts.sort(key=lambda alert: order.get(alert["severity"], 2))
    return alerts


# ------------------------------------------------------------------
# Baseline simulation
# ------------------------------------------------------------------

def _sorted_tasks(tasks):
    return sorted(
        tasks,
        key=lambda t: (
            PRIORITY_RANK.get(t.get("priority"), 4),
            -float(t.get("estimated_hours") or 0),
        ),
    )


def simulate_allocation(employees, tasks, strategy, seed=0, levels_by_employee=None):
    """Allocate tasks in memory with one strategy and return summary metrics.

    Strategies: 'random', 'round_robin', 'human_aware'. Nothing is written to
    the database.
    """
    if strategy not in STRATEGY_LABELS:
        raise ValueError(f"Unknown strategy: {strategy}")

    levels_by_employee = levels_by_employee or {}
    rng = random.Random(seed)

    loads = {e["employee_id"]: float(e.get("current_workload") or 0) for e in employees}
    pool = [dict(e) for e in employees if e.get("availability") == "Available"]

    round_robin_index = 0
    match_ratios = []
    no_match = 0
    unassigned = 0
    assigned = 0

    for task in _sorted_tasks(tasks):
        if not pool:
            unassigned += 1
            continue

        hours = float(task.get("estimated_hours") or 0)

        if strategy == "random":
            chosen = rng.choice(pool)
        elif strategy == "round_robin":
            chosen = pool[round_robin_index % len(pool)]
            round_robin_index += 1
        else:
            candidates = []
            for employee in pool:
                snapshot = {**employee, "current_workload": loads[employee["employee_id"]]}
                breakdown = score_breakdown(
                    snapshot, task, levels_by_employee.get(employee["employee_id"])
                )
                if breakdown["skill_match_ratio"] > 0:
                    candidates.append(
                        (breakdown["total"], -loads[employee["employee_id"]], employee)
                    )
            if not candidates:
                unassigned += 1
                continue
            candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
            chosen = candidates[0][2]

        ratio = skill_match_ratio(chosen.get("skills"), task.get("required_skills"))
        match_ratios.append(ratio)
        if ratio == 0:
            no_match += 1
        loads[chosen["employee_id"]] += hours
        assigned += 1

    utilization = {
        e["employee_id"]: utilization_pct(loads[e["employee_id"]], e.get("max_capacity"))
        for e in employees
    }
    values = list(utilization.values())

    return {
        "spread": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "max_util": max(values) if values else 0.0,
        "overloaded": sum(1 for value in values if value > 100),
        "avg_skill_match": (statistics.mean(match_ratios) * 100) if match_ratios else 0.0,
        "no_match": no_match,
        "unassigned": unassigned,
        "assigned": assigned,
        "utilization": utilization,
    }


def compare_strategies(employees, tasks, runs=200, seed=0, levels_by_employee=None):
    """Return {label: metrics}. The random baseline is averaged over many runs."""
    results = {}

    random_runs = [
        simulate_allocation(employees, tasks, "random", seed + i, levels_by_employee)
        for i in range(max(1, runs))
    ]
    averaged = {}
    for key in ("spread", "max_util", "overloaded", "avg_skill_match", "no_match", "unassigned", "assigned"):
        averaged[key] = statistics.mean(run[key] for run in random_runs)
    averaged["utilization"] = {
        employee["employee_id"]: statistics.mean(
            run["utilization"][employee["employee_id"]] for run in random_runs
        )
        for employee in employees
    }
    results[STRATEGY_LABELS["random"]] = averaged

    for key in ("round_robin", "human_aware"):
        results[STRATEGY_LABELS[key]] = simulate_allocation(
            employees, tasks, key, seed, levels_by_employee
        )
    return results

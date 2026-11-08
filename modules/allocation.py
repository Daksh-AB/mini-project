import sqlite3

from database import get_connection
from modules.extras import parse_skills, score_breakdown


def score_candidate(employee, task, levels=None):
    """Return an explainable recommendation row for one employee/task pair."""
    employee_data = dict(employee)
    task_data = dict(task)
    breakdown = score_breakdown(employee_data, task_data, levels)
    required = parse_skills(task_data.get("required_skills"))
    matched = parse_skills(employee_data.get("skills")) & required
    weighted = breakdown["weighted"]

    return {
        "employee_id": employee_data["employee_id"],
        "name": employee_data["name"],
        "matching_skills": ", ".join(sorted(matched)),
        "remaining_capacity": float(employee_data["max_capacity"])
        - float(employee_data["current_workload"]),
        "skill_score": round(weighted["skill"], 2),
        "capacity_score": round(weighted["workload"], 2),
        "experience_score": round(weighted["experience"], 2),
        "performance_score": round(weighted["performance"], 2),
        "total_score": round(breakdown["total"], 2),
    }


def get_recommendations(task_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM tasks WHERE task_id = ?",
        (task_id,)
    )

    task = cursor.fetchone()

    if not task:
        connection.close()
        return []

    estimated_hours = task["estimated_hours"]

    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()

    try:
        levels_by_employee = {}
        for row in cursor.execute(
            "SELECT employee_id, skill, level FROM skill_levels"
        ).fetchall():
            levels_by_employee.setdefault(row["employee_id"], {})[
                row["skill"]
            ] = row["level"]
    except sqlite3.OperationalError:
        levels_by_employee = {}

    recommendations = []

    for employee in employees:

        if employee["availability"] != "Available":
            continue

        remaining_capacity = (
            employee["max_capacity"] -
            employee["current_workload"]
        )

        if remaining_capacity < estimated_hours:
            continue

        breakdown = score_breakdown(
            dict(employee), dict(task), levels_by_employee.get(employee["employee_id"])
        )
        if breakdown["skill_match_ratio"] < 1:
            continue

        recommendations.append(
            score_candidate(
                employee,
                task,
                levels_by_employee.get(employee["employee_id"]),
            )
        )

    connection.close()

    recommendations.sort(
        key=lambda x: x["total_score"],
        reverse=True
    )

    return recommendations


def assign_task(task_id, employee_id):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # Lock writers before reading workload so concurrent allocators cannot
        # both pass the same capacity check.
        connection.execute("BEGIN IMMEDIATE")

        cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,)
        )

        task = cursor.fetchone()

        if not task:
            return False, "Task not found."

        if task["status"] != "Pending":
            return False, "Only pending tasks can be allocated."

        cursor.execute(
            "SELECT * FROM employees WHERE employee_id = ?",
            (employee_id,)
        )

        employee = cursor.fetchone()

        if not employee:
            return False, "Employee not found."

        if employee["availability"] != "Available":
            return False, "Employee is unavailable."

        new_workload = (
            employee["current_workload"] +
            task["estimated_hours"]
        )

        if new_workload > employee["max_capacity"]:
            return False, "Insufficient employee capacity."

        required_skills = {
            skill.strip().lower()
            for skill in task["required_skills"].split(",")
            if skill.strip()
        }

        employee_skills = {
            skill.strip().lower()
            for skill in employee["skills"].split(",")
            if skill.strip()
        }

        if not required_skills.issubset(employee_skills):
            return False, "Employee lacks required skills."

        cursor.execute("""
            INSERT INTO assignments
            (task_id, employee_id, status)
            VALUES (?, ?, 'Active')
        """, (task_id, employee_id))

        cursor.execute("""
            UPDATE tasks
            SET status = 'In Progress'
            WHERE task_id = ?
        """, (task_id,))

        cursor.execute("""
            UPDATE employees
            SET current_workload = ?
            WHERE employee_id = ?
        """, (new_workload, employee_id))

        connection.commit()

        return True, "Task allocated successfully!"

    except Exception as error:

        connection.rollback()
        return False, f"Allocation failed: {error}"

    finally:

        connection.close()

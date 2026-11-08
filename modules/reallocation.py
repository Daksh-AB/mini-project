import sqlite3

from database import get_connection
from modules.allocation import score_candidate
from modules.extras import score_breakdown


def get_affected_assignments():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            a.assignment_id,
            a.task_id,
            a.employee_id,
            e.name AS employee_name,
            e.availability,
            e.current_workload,
            t.title AS task_title,
            t.required_skills,
            t.estimated_hours,
            t.priority,
            t.status AS task_status
        FROM assignments a
        JOIN employees e
            ON a.employee_id = e.employee_id
        JOIN tasks t
            ON a.task_id = t.task_id
        WHERE a.status = 'Active'
          AND (
              e.availability = 'Unavailable'
              OR e.current_workload > e.max_capacity
          )
          AND t.status != 'Completed'
        ORDER BY a.assignment_id DESC
    """)

    assignments = cursor.fetchall()

    connection.close()

    return assignments


def get_replacement_recommendations(task_id, old_employee_id):

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

        if employee["employee_id"] == old_employee_id:
            continue

        if employee["availability"] != "Available":
            continue

        remaining_capacity = (
            employee["max_capacity"] -
            employee["current_workload"]
        )

        if remaining_capacity < task["estimated_hours"]:
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
        key=lambda item: item["total_score"],
        reverse=True
    )

    return recommendations


def approve_reallocation(task_id, old_employee_id, new_employee_id, reason):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # Serialize the read/check/update sequence with other reallocations.
        connection.execute("BEGIN IMMEDIATE")

        cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,)
        )

        task = cursor.fetchone()

        if not task or task["status"] == "Completed":
            return False, "Task is unavailable for reallocation."

        cursor.execute("""
            SELECT * FROM assignments
            WHERE task_id = ?
              AND employee_id = ?
              AND status = 'Active'
        """, (task_id, old_employee_id))

        old_assignment = cursor.fetchone()

        if not old_assignment:
            return False, "Active original assignment not found."

        cursor.execute(
            "SELECT * FROM employees WHERE employee_id = ?",
            (old_employee_id,)
        )

        old_employee = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM employees WHERE employee_id = ?",
            (new_employee_id,)
        )

        new_employee = cursor.fetchone()

        if not old_employee or not new_employee:
            return False, "Employee not found."

        if new_employee_id == old_employee_id:
            return False, "Choose a different employee."

        if new_employee["availability"] != "Available":
            return False, "Replacement employee is unavailable."

        required_skills = {
            skill.strip().lower()
            for skill in task["required_skills"].split(",")
            if skill.strip()
        }

        employee_skills = {
            skill.strip().lower()
            for skill in new_employee["skills"].split(",")
            if skill.strip()
        }

        if not required_skills.issubset(employee_skills):
            return False, "Replacement employee lacks required skills."

        task_hours = task["estimated_hours"]

        old_workload = old_employee["current_workload"]
        new_workload = new_employee["current_workload"]

        if new_workload + task_hours > new_employee["max_capacity"]:
            return False, "Replacement employee has insufficient capacity."

        # Close the old assignment.
        cursor.execute("""
            UPDATE assignments
            SET status = 'Reassigned'
            WHERE assignment_id = ?
        """, (old_assignment["assignment_id"],))

        # Create the new assignment.
        cursor.execute("""
            INSERT INTO assignments
            (task_id, employee_id, status)
            VALUES (?, ?, 'Active')
        """, (task_id, new_employee_id))

        # Update employee workloads.
        cursor.execute("""
            UPDATE employees
            SET current_workload = ?
            WHERE employee_id = ?
        """, (
            max(0, old_workload - task_hours),
            old_employee_id
        ))

        cursor.execute("""
            UPDATE employees
            SET current_workload = ?
            WHERE employee_id = ?
        """, (
            new_workload + task_hours,
            new_employee_id
        ))

        # Record reallocation history.
        cursor.execute("""
            INSERT INTO reallocation_history
            (task_id, old_employee_id, new_employee_id, reason)
            VALUES (?, ?, ?, ?)
        """, (
            task_id,
            old_employee_id,
            new_employee_id,
            reason
        ))

        connection.commit()

        return True, "Task successfully reallocated!"

    except Exception as error:

        connection.rollback()

        return False, f"Reallocation failed: {error}"

    finally:

        connection.close()

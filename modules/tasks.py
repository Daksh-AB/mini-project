import sqlite3

from database import get_connection
from modules.validation import validate_task


def add_task(
    title,
    description,
    required_skills,
    priority,
    estimated_hours,
    task_complexity=3
):

    errors = validate_task(
        title, required_skills, priority, estimated_hours, task_complexity
    )
    if errors:
        raise ValueError(" ".join(errors))

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO tasks
            (
                title, description, required_skills,
                priority, estimated_hours, status,
                task_complexity
            )
            VALUES (?, ?, ?, ?, ?, 'Pending', ?)
        """, (
            title,
            description,
            required_skills,
            priority,
            estimated_hours,
            task_complexity
        ))

        connection.commit()
        return "Task added successfully!"

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_all_tasks():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()

    connection.close()
    return tasks


def delete_task(task_id):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM tasks WHERE task_id = ?",
            (task_id,)
        )
    except sqlite3.IntegrityError:
        connection.close()
        return False

    connection.commit()
    deleted = cursor.rowcount
    connection.close()

    return deleted > 0


def update_task_status(task_id, status):

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,)
        )

        task = cursor.fetchone()

        if not task:
            return False

        old_status = task["status"]

        if old_status == "Completed" and status != "Completed":
            return False

        if old_status == "Completed":
            return True

        if status == "Completed":

            cursor.execute("""
                SELECT * FROM assignments
                WHERE task_id = ?
                  AND status = 'Active'
            """, (task_id,))

            assignment = cursor.fetchone()

            if assignment:

                employee_id = assignment["employee_id"]
                task_hours = task["estimated_hours"]

                cursor.execute("""
                    SELECT current_workload
                    FROM employees
                    WHERE employee_id = ?
                """, (employee_id,))

                employee = cursor.fetchone()

                if employee:

                    updated_workload = max(
                        0,
                        employee["current_workload"] - task_hours
                    )

                    cursor.execute("""
                        UPDATE employees
                        SET current_workload = ?
                        WHERE employee_id = ?
                    """, (
                        updated_workload,
                        employee_id
                    ))

                cursor.execute("""
                    UPDATE assignments
                    SET status = 'Completed'
                    WHERE assignment_id = ?
                """, (assignment["assignment_id"],))

        cursor.execute("""
            UPDATE tasks
            SET status = ?
            WHERE task_id = ?
        """, (status, task_id))

        connection.commit()
        return True

    except Exception:

        connection.rollback()
        return False

    finally:
        connection.close()

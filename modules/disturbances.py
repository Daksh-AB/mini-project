from database import get_connection


def report_unavailability(employee_id, description):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT * FROM employees WHERE employee_id = ?",
            (employee_id,)
        )

        employee = cursor.fetchone()

        if not employee:
            return False, "Employee not found."

        cursor.execute("""
            UPDATE employees
            SET availability = 'Unavailable'
            WHERE employee_id = ?
        """, (employee_id,))

        cursor.execute("""
            INSERT INTO disturbances
            (disturbance_type, employee_id, description)
            VALUES (?, ?, ?)
        """, (
            "Employee Unavailability",
            employee_id,
            description
        ))

        connection.commit()

        return True, f"{employee['name']} marked as unavailable."

    except Exception as error:
        connection.rollback()
        return False, str(error)

    finally:
        connection.close()


def report_workload_overload(employee_id, new_workload, description):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT * FROM employees WHERE employee_id = ?",
            (employee_id,)
        )

        employee = cursor.fetchone()

        if not employee:
            return False, "Employee not found."

        if new_workload <= employee["max_capacity"]:
            return False, "The entered workload does not exceed capacity."

        cursor.execute("""
            UPDATE employees
            SET current_workload = ?
            WHERE employee_id = ?
        """, (new_workload, employee_id))

        cursor.execute("""
            INSERT INTO disturbances
            (disturbance_type, employee_id, description)
            VALUES (?, ?, ?)
        """, (
            "Workload Overload",
            employee_id,
            description
        ))

        connection.commit()

        return True, f"Workload overload recorded for {employee['name']}."

    except Exception as error:
        connection.rollback()
        return False, str(error)

    finally:
        connection.close()


def report_task_delay(task_id, description):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,)
        )

        task = cursor.fetchone()

        if not task:
            return False, "Task not found."

        cursor.execute("""
            UPDATE tasks
            SET status = 'Delayed'
            WHERE task_id = ?
        """, (task_id,))

        cursor.execute("""
            INSERT INTO disturbances
            (disturbance_type, task_id, description)
            VALUES (?, ?, ?)
        """, (
            "Task Delay",
            task_id,
            description
        ))

        connection.commit()

        return True, f"Delay recorded for task: {task['title']}."

    except Exception as error:
        connection.rollback()
        return False, str(error)

    finally:
        connection.close()


def get_all_disturbances():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            d.disturbance_id,
            d.disturbance_type,
            e.name AS employee_name,
            t.title AS task_title,
            d.description,
            d.status,
            d.created_at
        FROM disturbances d
        LEFT JOIN employees e
            ON d.employee_id = e.employee_id
        LEFT JOIN tasks t
            ON d.task_id = t.task_id
        ORDER BY d.disturbance_id DESC
    """)

    disturbances = cursor.fetchall()

    connection.close()

    return disturbances
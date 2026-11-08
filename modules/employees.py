import sqlite3

from database import get_connection
from modules.validation import validate_employee


def add_employee(
    name,
    skills,
    availability="Available",
    max_capacity=40,
    current_workload=0,
    experience_years=0,
    historical_performance=1.0
):

    errors = validate_employee(
        name, skills, availability, max_capacity, current_workload,
        experience_years, historical_performance,
    )
    if errors:
        raise ValueError(" ".join(errors))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO employees
        (
            name, skills, availability, max_capacity,
            current_workload, experience_years,
            historical_performance
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        skills,
        availability,
        max_capacity,
        current_workload,
        experience_years,
        historical_performance
    ))

    connection.commit()
    connection.close()

    return "Employee added successfully!"


def get_all_employees():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM employees")

    employees = cursor.fetchall()

    connection.close()

    return employees


def delete_employee(employee_id):

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "DELETE FROM employees WHERE employee_id = ?",
            (employee_id,)
        )
    except sqlite3.IntegrityError:
        connection.close()
        return False

    connection.commit()

    deleted = cursor.rowcount

    connection.close()

    return deleted > 0


def update_employee(
    employee_id,
    name,
    skills,
    availability,
    max_capacity,
    current_workload,
    experience_years=0,
    historical_performance=1.0
):

    errors = validate_employee(
        name, skills, availability, max_capacity, current_workload,
        experience_years, historical_performance,
    )
    if errors:
        raise ValueError(" ".join(errors))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE employees
        SET name = ?,
            skills = ?,
            availability = ?,
            max_capacity = ?,
            current_workload = ?,
            experience_years = ?,
            historical_performance = ?
        WHERE employee_id = ?
    """, (
        name,
        skills,
        availability,
        max_capacity,
        current_workload,
        experience_years,
        historical_performance,
        employee_id
    ))

    connection.commit()

    updated = cursor.rowcount

    connection.close()

    return updated > 0

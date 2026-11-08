"""Persistence and evaluation helpers for model predictions."""

import json

from database import get_connection


def record_prediction(
    task_id,
    employee_id,
    model_version,
    predicted_hours,
    inputs,
    conn=None,
):
    owned = conn is None
    connection = conn or get_connection()
    try:
        connection.execute(
            """
            INSERT INTO prediction_history
                (task_id, employee_id, model_version, predicted_hours, input_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_id,
                employee_id,
                model_version,
                float(predicted_hours),
                json.dumps(inputs, sort_keys=True),
            ),
        )
        connection.commit()
    finally:
        if owned:
            connection.close()


def get_prediction_records(conn=None):
    owned = conn is None
    connection = conn or get_connection()
    try:
        rows = connection.execute(
            """
            SELECT p.prediction_id, p.task_id, p.employee_id,
                   p.model_version, p.predicted_hours, p.input_json,
                   p.created_at, t.actual_hours, t.estimated_hours
            FROM prediction_history p
            LEFT JOIN tasks t ON t.task_id = p.task_id
            ORDER BY p.prediction_id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        if owned:
            connection.close()

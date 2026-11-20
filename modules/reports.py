"""Period-based operational reports for the dashboard."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

import pandas as pd


PERIODS = ("Weekly", "Monthly", "Quarterly")


def period_bounds(period: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return an inclusive start and exclusive end for a named calendar period."""
    if period not in PERIODS:
        raise ValueError(f"Period must be one of: {', '.join(PERIODS)}")
    current = now or datetime.now()
    day = current.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "Weekly":
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=7)
    elif period == "Monthly":
        start = day.replace(day=1)
        last_day = calendar.monthrange(start.year, start.month)[1]
        end = (start.replace(day=last_day) + timedelta(days=1))
    else:
        quarter_month = ((day.month - 1) // 3) * 3 + 1
        start = day.replace(month=quarter_month, day=1)
        if quarter_month == 10:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=quarter_month + 3)
    return start, end


def _rows(connection, query, params=()):
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def build_report(connection, period: str, now: datetime | None = None) -> dict:
    """Build a report from timestamped events plus current-state snapshots."""
    start, end = period_bounds(period, now)
    start_text = start.isoformat(sep=" ")
    end_text = end.isoformat(sep=" ")
    assignments = _rows(connection, """
        SELECT a.assignment_id, a.task_id, t.title AS task_title,
               e.name AS employee_name, a.assigned_at, a.status,
               t.priority, t.estimated_hours
        FROM assignments a
        LEFT JOIN tasks t ON t.task_id = a.task_id
        LEFT JOIN employees e ON e.employee_id = a.employee_id
        WHERE a.assigned_at >= ? AND a.assigned_at < ?
        ORDER BY a.assigned_at
    """, (start_text, end_text))
    reallocations = _rows(connection, """
        SELECT h.history_id, t.title AS task_title,
               old_e.name AS previous_employee, new_e.name AS new_employee,
               h.reason, h.changed_at
        FROM reallocation_history h
        LEFT JOIN tasks t ON t.task_id = h.task_id
        LEFT JOIN employees old_e ON old_e.employee_id = h.old_employee_id
        LEFT JOIN employees new_e ON new_e.employee_id = h.new_employee_id
        WHERE h.changed_at >= ? AND h.changed_at < ?
        ORDER BY h.changed_at
    """, (start_text, end_text))
    disturbances = _rows(connection, """
        SELECT disturbance_id, disturbance_type, description, status, created_at
        FROM disturbances
        WHERE created_at >= ? AND created_at < ?
        ORDER BY created_at
    """, (start_text, end_text))
    predictions = _rows(connection, """
        SELECT p.prediction_id, p.predicted_hours, p.created_at,
               t.estimated_hours, t.actual_hours
        FROM prediction_history p
        LEFT JOIN tasks t ON t.task_id = p.task_id
        WHERE p.created_at >= ? AND p.created_at < ?
        ORDER BY p.created_at
    """, (start_text, end_text))

    employees = _rows(connection, "SELECT current_workload, max_capacity FROM employees")
    tasks = _rows(connection, "SELECT status FROM tasks")
    completed = sum(task["status"] == "Completed" for task in tasks)
    observed = [p for p in predictions if p["actual_hours"] is not None]
    model_mae = (
        sum(abs(float(p["predicted_hours"]) - float(p["actual_hours"])) for p in observed)
        / len(observed)
        if observed else None
    )
    summary = {
        "assignments": len(assignments),
        "reallocations": len(reallocations),
        "disturbances": len(disturbances),
        "predictions": len(predictions),
        "observed_predictions": len(observed),
        "model_mae_hours": model_mae,
        "current_task_completion_rate": completed / len(tasks) * 100 if tasks else 0,
        "current_average_utilization": (
            sum(float(row["current_workload"] or 0) / float(row["max_capacity"] or 1) * 100
                for row in employees) / len(employees)
            if employees else 0
        ),
    }
    return {
        "period": period,
        "start": start,
        "end": end,
        "summary": summary,
        "assignments": assignments,
        "reallocations": reallocations,
        "disturbances": disturbances,
        "predictions": predictions,
    }


def report_csv_frames(report: dict) -> dict[str, pd.DataFrame]:
    """Return stable, download-ready dataframes for report sections."""
    summary = dict(report["summary"])
    summary.update({"period": report["period"], "start": report["start"], "end": report["end"]})
    return {
        "summary": pd.DataFrame([summary]),
        "assignments": pd.DataFrame(report["assignments"]),
        "reallocations": pd.DataFrame(report["reallocations"]),
        "disturbances": pd.DataFrame(report["disturbances"]),
        "predictions": pd.DataFrame(report["predictions"]),
    }

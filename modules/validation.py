"""Shared validation for service-layer inputs."""


VALID_AVAILABILITY = {"Available", "Unavailable"}
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}


def validate_employee(
    name,
    skills,
    availability="Available",
    max_capacity=40,
    current_workload=0,
    experience_years=0,
    historical_performance=1.0,
):
    errors = []
    if not str(name or "").strip():
        errors.append("Employee name is required.")
    if not str(skills or "").strip():
        errors.append("At least one skill is required.")
    if availability not in VALID_AVAILABILITY:
        errors.append("Availability must be Available or Unavailable.")
    try:
        capacity = float(max_capacity)
        workload = float(current_workload)
        experience = float(experience_years)
        performance = float(historical_performance)
    except (TypeError, ValueError):
        return errors + ["Employee numeric fields must be valid numbers."]

    if capacity <= 0:
        errors.append("Maximum capacity must be greater than zero.")
    if workload < 0:
        errors.append("Current workload cannot be negative.")
    if capacity > 0 and workload > capacity:
        errors.append("Current workload cannot exceed maximum capacity.")
    if experience < 0:
        errors.append("Experience cannot be negative.")
    if not 0.5 <= performance <= 1.5:
        errors.append("Historical performance must be between 0.5 and 1.5.")
    return errors


def validate_task(title, required_skills, priority, estimated_hours, task_complexity=3):
    errors = []
    if not str(title or "").strip():
        errors.append("Task title is required.")
    if not str(required_skills or "").strip():
        errors.append("At least one required skill is needed.")
    if priority not in VALID_PRIORITIES:
        errors.append("Priority must be Low, Medium, High, or Critical.")
    try:
        hours = float(estimated_hours)
        complexity = float(task_complexity)
    except (TypeError, ValueError):
        return errors + ["Task numeric fields must be valid numbers."]
    if hours <= 0:
        errors.append("Estimated hours must be greater than zero.")
    if not 1 <= complexity <= 5:
        errors.append("Task complexity must be between 1 and 5.")
    return errors

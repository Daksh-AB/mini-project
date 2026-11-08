# Human-Aware Task Allocation Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current Streamlit prototype into a reliable, documented team application with consistent allocation logic, auditable task history, trustworthy prediction reporting, and repeatable verification.

**Architecture:** Keep Streamlit and SQLite, but move shared business rules into service modules and keep UI code focused on rendering and input handling. Use additive schema migrations, parameterized SQL, explicit transactions, and a small unittest suite. Keep the existing ML model interface while adding real-task evaluation records and baseline comparisons.

**Tech Stack:** Python 3.12, Streamlit, SQLite, pandas, Plotly, scikit-learn, joblib, unittest.

**Spec:** This plan implements the project review priorities agreed in the conversation: authentication, dependency/setup documentation, SQLite integrity, transaction-safe allocation, consistent scoring, real evaluation hooks, tests, maintainability, and deployment readiness.

## Global Constraints

- Preserve the current Streamlit user flows and saved model input schema.
- Do not delete or rewrite existing user data during migrations.
- Keep all SQL parameterized except fixed internal table/column identifiers.
- Use tests before production changes for new behavior.
- Treat synthetic ML metrics as demonstration-only until real task history exists.

## Review Focus

- Existing databases missing optional tables or columns: startup must migrate safely.
- Deleting referenced employees/tasks: return a safe failure without corrupting history.
- Concurrent allocation/reallocation: capacity must never be consumed twice.
- Invalid direct service inputs: reject negative, malformed, or out-of-range values.
- Missing or stale model artifacts: prediction UI must degrade safely and report the cause.

### Task 1: Centralize validation and database migrations

**Files:**
- Modify: `database.py`, `modules/employees.py`, `modules/tasks.py`, `modules/extras.py`
- Test: `tests/test_database.py`, `tests/test_validation.py`

Add schema version tracking, idempotent migrations, and shared validation for employee/task inputs. Verify old schemas, invalid inputs, and safe referenced deletes.

### Task 2: Complete service-layer test coverage

**Files:**
- Test: `tests/test_tasks.py`, `tests/test_reallocation.py`, `tests/test_disturbances.py`, `tests/test_scoring.py`

Cover status transitions, workload reconciliation, disturbance updates, reallocation history, skill parsing, dependency cycles, and edge cases. Keep tests runnable with `python -m unittest discover -s tests -v`.

### Task 3: Add prediction history and real evaluation

**Files:**
- Modify: `database.py`, `modules/prediction.py`, `modules/extras.py`, `app.py`
- Create: `modules/modeling.py`
- Test: `tests/test_prediction.py`, `tests/test_modeling.py`

Record each prediction with inputs, model version, predicted hours, and later actual hours. Add model loading validation, cached loading, baseline MAE comparison, and an analytics view that reports only observed records.

### Task 4: Finish allocation and fairness analytics

**Files:**
- Modify: `modules/allocation.py`, `modules/reallocation.py`, `modules/analytics.py`, `app.py`
- Test: `tests/test_allocation_scoring.py`, `tests/test_analytics.py`

Expose score components, compare human-aware allocation against random and round-robin baselines, and make the dashboard clearly distinguish descriptive fairness indicators from measured outcomes.

### Task 5: Reduce UI coupling and improve operations

**Files:**
- Create: `ui/theme.py`, `ui/components.py`, `pages/`
- Modify: `app.py`, `README.md`, `requirements.txt`, `.gitignore`

Extract shared UI helpers and page sections incrementally, add structured logging and a health check, document backups and deployment, and remove stale runtime artifacts from normal development.

### Task 6: Final verification and handoff

**Files:**
- Test: all files under `tests/`

Run the complete unittest suite, compileall, database initialization against a copy, model prediction smoke checks, and a Streamlit startup check. Update README with exact verification commands and known limitations.

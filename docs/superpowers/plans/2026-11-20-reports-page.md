# Reports Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a separate Reports page with weekly, monthly, and quarterly operational summaries and CSV downloads.

**Architecture:** Keep report calculations in a focused `modules/reports.py` module and keep Streamlit rendering in the existing `app.py` navigation flow. Use existing timestamped assignment, reallocation, disturbance, and prediction records; label current employee/task metrics as snapshots.

**Tech Stack:** Python, pandas, SQLite connection helpers, Streamlit, existing Plotly setup, unittest.

**Spec:** `docs/superpowers/specs/2026-11-20-reports-page-design.md`

## Global Constraints

- Do not add a new dependency.
- Do not invent historical timestamps for records that do not store them.
- Keep the existing Analytics page behavior unchanged.
- Use native Streamlit controls and CSV downloads.

## Review Focus

- Period boundaries must include the start date and exclude records after the end date.
- Weekly, monthly, and quarterly periods must be calculated from the current date consistently.
- Empty periods must render zero-valued summaries and downloadable CSVs without errors.
- Current workload/task-status metrics must be labeled as snapshots, not historical period events.
- CSV output must contain stable column names and be generated without exposing credentials.

### Task 1: Report calculation helpers

**Files:**
- Create: `modules/reports.py`
- Test: `tests/test_reports.py`

**Interfaces:**
- `period_bounds(period: str, now: datetime | None = None) -> tuple[datetime, datetime]`
- `build_report(connection, period: str, now: datetime | None = None) -> dict`
- `report_csv_frames(report: dict) -> dict[str, pandas.DataFrame]`

- [ ] Write tests for period boundaries, empty periods, and timestamp-filtered assignment/reallocation/disturbance/prediction records.
- [ ] Implement the helpers using parameterized queries and existing connection row factories.
- [ ] Run `python -m unittest tests.test_reports -v`.

### Task 2: Reports navigation and UI

**Files:**
- Modify: `app.py` navigation list and page rendering

**Interfaces:**
- Consume `build_report` and `report_csv_frames` from `modules.reports`.

- [ ] Add a Reports item beside Analytics in the existing navigation.
- [ ] Render a Weekly / Monthly / Quarterly selector, period dates, KPI cards, charts/tables, snapshot labels, and CSV download buttons.
- [ ] Preserve existing authorization and page styling conventions.

### Task 3: Verification and documentation

**Files:**
- Modify: `README.md`

- [ ] Document the Reports page and its timestamp limitations.
- [ ] Run `python -m unittest discover -s tests -q` using `.venv`.
- [ ] Run `python -m compileall -q app.py modules tests`.
- [ ] Start the app locally and verify the Reports page loads for all three periods.


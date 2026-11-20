# Human-Aware Task Allocation

A Streamlit workspace for assigning tasks using employee skills, availability,
workload, experience, and historical performance. It also includes disturbance
reporting, dynamic task reallocation, analytics, and completion-time prediction.

## Requirements

- Python 3.12 or newer
- Windows PowerShell, macOS, or Linux

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the pinned dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Configure authentication

The first manager account is created automatically when the app starts. You
can set its username and initial password before the first launch:

```powershell
$env:TASK_APP_USERNAME = "manager"
$env:TASK_APP_PASSWORD = "choose-a-strong-initial-password"
```

If these variables are not set, the development defaults are used. The first
login is required to choose a new password. Passwords are stored as PBKDF2
hashes, not plaintext values.

## Run the app

```powershell
streamlit run app.py
```

The sidebar shows a runtime status check for the SQLite database and trained
model artifact. A missing model is expected until the training command has been
run; the rest of the workspace remains usable.

The app creates or upgrades `task_allocation.db` on startup. Keep this file
private and back it up before making schema changes.

## Use PostgreSQL in deployment

Set `DATABASE_URL` to a PostgreSQL connection string (for example, a Neon
pooled URL) in the deployment platform's secrets. When `DATABASE_URL` is set,
the app uses PostgreSQL; otherwise it keeps using local SQLite. To copy an
existing local database into the PostgreSQL database, set `DATABASE_URL` in
PowerShell and run:

```powershell
python scripts/migrate_sqlite_to_postgres.py
```

Never commit the connection string or place it in `.env` files tracked by Git.

## Train the completion-time model

Generate the included synthetic training data when needed:

```powershell
python data/generate_dataset.py
```

Train and save the model:

```powershell
python models/train_model.py
```

The model is saved to `models/completion_time_model.pkl` and its evaluation is
written to `models/model_evaluation.json`.

The included dataset is synthetic and is useful for demonstrating the flow. Its
metrics should not be treated as evidence of real-world prediction accuracy.

To evaluate predictions on observed work, edit a task after it is completed and
enter its `Actual Hours`. The Analytics page then compares model MAE with the
original estimate MAE using only tasks that have both a recorded prediction and
an actual duration.

The Reports page provides Weekly, Monthly, and Quarterly views. Event counts
use stored assignment, reallocation, disturbance, and prediction timestamps.
Current task completion and employee utilization are labeled snapshots because
older records do not include historical state timestamps. Each report section
can be downloaded as CSV.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Back up the database

Create a consistent SQLite backup while the app is running:

```powershell
python scripts/backup_database.py
```

Backups are written to `backups/`. To choose a path explicitly:

```powershell
python scripts/backup_database.py backups\before-migration.db
```

## Deploy on Render with persistent storage

The repository includes `render.yaml` for a single-instance Render deployment.
It mounts a persistent disk at `/var/data` and stores `task_allocation.db` there.
Create the service from the repository, set `TASK_APP_USERNAME` and
`TASK_APP_PASSWORD` as secret environment variables, and deploy. The persistent
disk is intended for a small team; use PostgreSQL before running multiple app
instances.

## Main project areas

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit UI and page routing |
| `database.py` | SQLite connection and core schema |
| `modules/` | Employees, tasks, allocation, disturbances, reallocation, auth |
| `data/` | Synthetic dataset generation and training data |
| `models/` | Model training, saved model, and evaluation report |
| `tests/` | Automated tests |

## Current limitations

- The model is trained on synthetic data until real completed-task history is
  available.
- SQLite is intended for a small deployment or local prototype.
- Allocation quality should be evaluated against a real baseline before making
  productivity or fairness claims.

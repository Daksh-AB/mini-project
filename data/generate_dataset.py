import pandas as pd
import numpy as np

from pathlib import Path

# Reproducibility
np.random.seed(42)

NUMBER_OF_RECORDS = 5000

# ---------------------------------------
# GENERATE TASK CHARACTERISTICS
# ---------------------------------------

estimated_hours = np.random.uniform(2, 40, NUMBER_OF_RECORDS)

priority = np.random.choice(
    [1, 2, 3],
    NUMBER_OF_RECORDS,
    p=[0.25, 0.45, 0.30]
)

task_complexity = np.random.randint(
    1, 6, NUMBER_OF_RECORDS
)

required_skill_count = np.random.randint(
    1, 7, NUMBER_OF_RECORDS
)

# ---------------------------------------
# GENERATE EMPLOYEE CHARACTERISTICS
# ---------------------------------------

workload_ratio = np.random.uniform(
    0.1, 1.2, NUMBER_OF_RECORDS
)

experience_years = np.random.uniform(
    0, 15, NUMBER_OF_RECORDS
)

skill_match_ratio = np.random.uniform(
    0.3, 1.0, NUMBER_OF_RECORDS
)

historical_performance = np.random.uniform(
    0.7, 1.3, NUMBER_OF_RECORDS
)

# ---------------------------------------
# CALCULATE COMPLETION TIME
# ---------------------------------------

workload_factor = 1 + workload_ratio * 0.25

priority_factor = 1 + (priority - 2) * 0.05

complexity_factor = 1 + task_complexity * 0.08

skill_factor = 1 + required_skill_count * 0.025

experience_factor = 1 - np.minimum(
    experience_years * 0.012, 0.15
)

skill_match_factor = 1 + (
    1 - skill_match_ratio
) * 0.35

performance_factor = 1 / historical_performance

actual_hours = (
    estimated_hours
    * workload_factor
    * priority_factor
    * complexity_factor
    * skill_factor
    * experience_factor
    * skill_match_factor
    * performance_factor
    + np.random.normal(0, 2, NUMBER_OF_RECORDS)
)

actual_hours = np.maximum(actual_hours, 0.5)

# ---------------------------------------
# CREATE DATASET
# ---------------------------------------

data = pd.DataFrame({

    "estimated_hours": estimated_hours,

    "priority": priority,

    "workload_ratio": workload_ratio,

    "required_skill_count": required_skill_count,

    "task_complexity": task_complexity,

    "experience_years": experience_years,

    "skill_match_ratio": skill_match_ratio,

    "historical_performance": historical_performance,

    "actual_hours": actual_hours
})

# ---------------------------------------
# SAVE DATASET
# ---------------------------------------

output_path = (
    Path(__file__).resolve().parent
    / "training_data.csv"
)

data.to_csv(output_path, index=False)

print("\n====================================")
print(" ADVANCED DATASET GENERATED")
print("====================================")

print(f"\nTotal records: {len(data)}")

print("\nFeatures generated:")

for column in data.columns:
    if column != "actual_hours":
        print("-", column)

print("\nDataset statistics:")
print(data.describe().round(2))

print("\nDataset saved successfully!")
print(output_path)
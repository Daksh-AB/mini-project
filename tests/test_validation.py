import unittest

from modules.validation import validate_employee, validate_task


class ValidationTests(unittest.TestCase):
    def test_employee_validation_rejects_negative_capacity_and_workload(self):
        errors = validate_employee(
            name="Asha",
            skills="python",
            availability="Available",
            max_capacity=-1,
            current_workload=-2,
            experience_years=1,
            historical_performance=1,
        )
        self.assertIn("Maximum capacity must be greater than zero.", errors)
        self.assertIn("Current workload cannot be negative.", errors)

    def test_task_validation_rejects_invalid_priority_and_hours(self):
        errors = validate_task(
            title="Build",
            required_skills="python",
            priority="Urgent",
            estimated_hours=0,
            task_complexity=6,
        )
        self.assertIn("Priority must be Low, Medium, High, or Critical.", errors)
        self.assertIn("Estimated hours must be greater than zero.", errors)
        self.assertIn("Task complexity must be between 1 and 5.", errors)


if __name__ == "__main__":
    unittest.main()

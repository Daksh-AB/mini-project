"""Load sample employees and tasks for the demonstration.

Run from the project folder:   python seed_demo.py

It uses the project's own add_employee / add_task functions, skips anything that
already exists (so it is safe to run twice) and does NOT create assignments or
disturbances - you create those live during the demo:

  1. Initial Task Allocation  -> allocate a task
  2. Disturbance Management   -> mark that employee unavailable
  3. Dynamic Reallocation     -> approve a replacement
"""

from database import init_db
from modules.employees import add_employee, get_all_employees
from modules.tasks import add_task, get_all_tasks

EMPLOYEES = [
    # name, skills, availability, capacity, workload, experience, performance
    ("Aarav Sharma", "Python, SQL, Machine Learning", "Available", 40, 12, 6.0, 1.15),
    ("Diya Patel", "Python, SQL, Data Analysis", "Available", 40, 20, 4.0, 1.05),
    ("Rohan Mehta", "Java, Spring, SQL", "Available", 40, 28, 5.0, 1.00),
    ("Ishita Rao", "React, JavaScript, CSS", "Available", 35, 10, 3.0, 1.10),
    ("Kabir Nair", "JavaScript, React, Python", "Available", 40, 34, 2.0, 0.95),
    ("Meera Iyer", "Testing, Python, Documentation", "Available", 30, 8, 3.5, 1.00),
]

TASKS = [
    # title, description, required skills, priority, hours, complexity
    ("Build REST API", "Create the backend API for the order system.", "Python, SQL", "High", 16, 3.5),
    ("Train churn model", "Train and evaluate a churn prediction model.", "Python, Machine Learning", "High", 24, 4.5),
    ("Design dashboard UI", "Responsive dashboard screens.", "React, CSS", "Medium", 14, 3.0),
    ("Database optimisation", "Tune slow queries and add indexes.", "SQL", "Critical", 10, 4.0),
    ("Customer data cleaning", "Clean and validate customer records.", "Python, Data Analysis", "Medium", 12, 2.5),
    ("Payment module", "Integrate the payment service.", "Java, Spring", "High", 20, 4.0),
    ("Write test suite", "Automated tests for the API.", "Testing, Python", "Low", 9, 2.0),
    ("User guide", "Documentation for end users.", "Documentation", "Low", 6, 1.5),
]


def main():
    init_db()

    existing_employees = {str(e["name"]).strip().lower() for e in get_all_employees()}
    added_employees = 0
    for name, skills, availability, capacity, workload, experience, performance in EMPLOYEES:
        if name.lower() in existing_employees:
            continue
        add_employee(name, skills, availability, capacity, workload, experience, performance)
        added_employees += 1

    existing_tasks = {str(t["title"]).strip().lower() for t in get_all_tasks()}
    added_tasks = 0
    for title, description, skills, priority, hours, complexity in TASKS:
        if title.lower() in existing_tasks:
            continue
        add_task(title, description, skills, priority, hours, complexity)
        added_tasks += 1

    print(f"Added {added_employees} employee(s) and {added_tasks} task(s).")


if __name__ == "__main__":
    main()
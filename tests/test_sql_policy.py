import pytest

from insightsql.errors import SQLPolicyError
from insightsql.sql_policy import validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE employees",
        "DELETE FROM employees",
        "UPDATE employees SET job_title = 'x'",
        "ALTER TABLE employees ADD COLUMN x TEXT",
        "TRUNCATE employees",
        "INSERT INTO employees (email) VALUES ('x')",
        "SELECT 1; DROP TABLE employees",
        "SELECT * FROM employees",
        "SELECT first_name FROM employees",
        "SELECT email FROM employees",
        "SELECT employee_id FROM employees",
        "SELECT load_extension('bad')",
        "SELECT * FROM sqlite_master",
    ],
)
def test_rejects_mutating_or_unsafe_sql(sql: str) -> None:
    with pytest.raises(SQLPolicyError):
        validate_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT department_id, COUNT(employee_id) AS headcount FROM employees GROUP BY department_id",
        "SELECT d.name, COUNT(e.employee_id) AS headcount FROM departments AS d JOIN employees AS e ON e.department_id = d.department_id GROUP BY d.name",
        "WITH totals AS (SELECT department_id, COUNT(employee_id) AS headcount FROM employees GROUP BY department_id) SELECT d.name, t.headcount FROM totals AS t JOIN departments AS d ON d.department_id = t.department_id",
    ],
)
def test_accepts_approved_read_only_selects(sql: str) -> None:
    assert validate_sql(sql) == sql


def test_rejects_queries_over_maximum_sql_length() -> None:
    with pytest.raises(SQLPolicyError, match="too long"):
        validate_sql("SELECT 1 -- " + "x" * 20_000)
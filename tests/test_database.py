import sqlite3

import pytest

from insightsql.database import execute_readonly_query, initialize_database
from insightsql.errors import QueryLimitError, SQLPolicyError


@pytest.fixture
def seeded_database(tmp_path):
    database_path = tmp_path / "insightsql.db"
    initialize_database(database_path, include_seed=True)
    return database_path


def test_seeded_database_has_expected_rows_and_valid_foreign_keys(seeded_database) -> None:
    result = execute_readonly_query(
        "SELECT 'departments' AS table_name, COUNT(*) AS row_count FROM departments "
        "UNION ALL SELECT 'employees', COUNT(*) FROM employees "
        "UNION ALL SELECT 'projects', COUNT(*) FROM projects",
        seeded_database,
    )
    assert {row[0]: row[1] for row in result.rows} == {
        "departments": 5,
        "employees": 20,
        "projects": 10,
    }
    with sqlite3.connect(seeded_database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM employees",
        "UPDATE employees SET job_title = 'x'",
        "DROP TABLE employees",
        "INSERT INTO departments (department_code, name, location) VALUES ('X', 'X', 'X')",
    ],
)
def test_execution_never_runs_mutating_sql(seeded_database, sql: str) -> None:
    with pytest.raises(SQLPolicyError):
        execute_readonly_query(sql, seeded_database)


def test_execution_rejects_columns_outside_the_data_allowlist(seeded_database) -> None:
    with pytest.raises(SQLPolicyError, match="personal details"):
        execute_readonly_query("SELECT email FROM employees", seeded_database)


def test_execution_enforces_result_limit(seeded_database) -> None:
    with pytest.raises(QueryLimitError, match="display limit"):
        execute_readonly_query("SELECT name FROM departments", seeded_database, max_rows=2)


def test_read_only_execution_does_not_change_database(seeded_database) -> None:
    execute_readonly_query("SELECT COUNT(*) FROM employees", seeded_database)
    with sqlite3.connect(seeded_database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 20


def test_string_literals_are_bound_and_hidden_from_visible_sql(seeded_database) -> None:
    result = execute_readonly_query(
        "SELECT name FROM departments WHERE department_code = 'ENG'",
        seeded_database,
    )
    assert result.rows == (("Engineering",),)
    assert result.sql == "SELECT name FROM departments WHERE department_code = :p0"
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from insightsql.errors import QueryExecutionError, QueryLimitError, SQLPolicyError
from insightsql.sql_policy import ALLOWED_FUNCTIONS, ALLOWED_TABLES, prepare_sql

LOGGER = logging.getLogger("insightsql.database")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "database_schema.sql"
SEED_MARKER = "-- Sample data begins here (development/demo only)."
READABLE_COLUMNS = {
    "departments": {"department_id", "department_code", "name", "location"},
    "employees": {"employee_id", "department_id", "job_title", "hire_date", "employment_status"},
    "projects": {"project_id", "department_id", "project_code", "name", "start_date", "end_date", "status"},
    "employee_projects": {
        "employee_id", "project_id", "project_role", "assigned_on", "released_on", "allocation_pct",
    },
}
@dataclass(frozen=True, slots=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    sql: str


def initialize_database(database_path: Path, *, include_seed: bool = False) -> None:
    if database_path.exists() and database_path.stat().st_size > 0:
        raise FileExistsError(f"Database already exists: {database_path}")
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"SQLite schema not found: {SCHEMA_PATH}")

    script = SCHEMA_PATH.read_text(encoding="utf-8")
    if not include_seed:
        if SEED_MARKER not in script:
            raise RuntimeError("The database seed marker is missing from the schema script.")
        script = script.split(SEED_MARKER, maxsplit=1)[0] + "\nCOMMIT;\n"

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(script)
    except sqlite3.DatabaseError:
        connection.rollback()
        raise
    finally:
        connection.close()
    LOGGER.info("database_initialized", extra={"seeded": include_seed})


def ensure_database(database_path: Path) -> None:
    if not database_path.exists():
        initialize_database(database_path)
        return

    database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(database_uri, uri=True) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
    except sqlite3.DatabaseError as exc:
        raise QueryExecutionError("The SQLite database could not be opened.") from exc
    if not ALLOWED_TABLES.issubset(table_names):
        raise QueryExecutionError("The SQLite database is missing required InsightSQL tables.")


def _authorize_read(
    action: int,
    argument_one: str | None,
    argument_two: str | None,
    database_name: str | None,
    trigger_name: str | None,
) -> int:
    del database_name, trigger_name
    if action in {sqlite3.SQLITE_SELECT, getattr(sqlite3, "SQLITE_RECURSIVE", -1)}:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        table_name = (argument_one or "").lower()
        column_name = (argument_two or "").lower()
        if table_name in ALLOWED_TABLES and (
            not column_name or column_name in READABLE_COLUMNS[table_name]
        ):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        function_name = (argument_two or argument_one or "").lower()
        return sqlite3.SQLITE_OK if function_name in ALLOWED_FUNCTIONS else sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_DENY


def execute_readonly_query(
    sql: str,
    database_path: Path,
    *,
    max_rows: int = 500,
    timeout_seconds: float = 5.0,
) -> QueryResult:
    approved_sql, parameters = prepare_sql(sql)
    if not database_path.is_file():
        raise QueryExecutionError("The SQLite database is not available.")

    database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    connection: sqlite3.Connection | None = None
    deadline = time.monotonic() + timeout_seconds
    try:
        connection = sqlite3.connect(database_uri, uri=True, timeout=timeout_seconds)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(_authorize_read)
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        cursor = connection.execute(approved_sql, parameters)
        columns = tuple(item[0] for item in (cursor.description or ()))
        rows = cursor.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            raise QueryLimitError(f"The result exceeds the {max_rows:,}-row display limit. Narrow your question.")
        return QueryResult(columns, tuple(tuple(row) for row in rows), approved_sql)
    except (SQLPolicyError, QueryLimitError):
        raise
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise QueryLimitError("The query took too long to complete. Try a narrower question.") from exc
        if "not authorized" in str(exc).lower():
            raise SQLPolicyError("The query attempted to access data or a SQLite feature that is not allowed.") from exc
        LOGGER.warning("sqlite_query_rejected", extra={"error_type": type(exc).__name__})
        raise QueryExecutionError("SQLite could not run the generated query. Try rephrasing it.") from exc
    except sqlite3.DatabaseError as exc:
        LOGGER.warning("sqlite_query_failed", extra={"error_type": type(exc).__name__})
        raise QueryExecutionError("The database could not complete that query.") from exc
    finally:
        if connection is not None:
            connection.close()
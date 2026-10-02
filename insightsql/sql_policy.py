from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from insightsql.errors import SQLPolicyError

ALLOWED_TABLES = frozenset({"departments", "employees", "projects", "employee_projects"})
ALLOWED_FUNCTIONS = frozenset(
    {
        "abs", "avg", "coalesce", "count", "date", "datetime", "ifnull", "julianday", "length",
        "lower", "ltrim", "max", "min", "nullif", "printf", "replace", "round", "rtrim",
        "strftime", "substr", "sum", "time", "total", "trim", "typeof", "upper",
    }
)
DIRECT_IDENTIFIER_COLUMNS = frozenset(
    {"employee_id", "manager_id", "email", "first_name", "last_name"}
)
MAX_SQL_LENGTH = 20_000


def _contains_direct_identifier(select: exp.Select) -> bool:
    for projection in select.expressions:
        for column in projection.find_all(exp.Column):
            if column.name.lower() not in DIRECT_IDENTIFIER_COLUMNS:
                continue

            parent = column.parent
            inside_count = False
            while parent is not None and not isinstance(parent, exp.Select):
                if isinstance(parent, exp.Count):
                    inside_count = True
                    break
                parent = parent.parent
            if not inside_count:
                return True
    return False


def validate_sql(sql: str) -> str:
    candidate = sql.strip()
    if not candidate:
        raise SQLPolicyError("The assistant did not provide a query. Please rephrase your question.")
    if len(candidate) > MAX_SQL_LENGTH:
        raise SQLPolicyError("The generated query is too long to run safely.")

    try:
        statements = [statement for statement in sqlglot.parse(candidate, read="sqlite") if statement]
    except ParseError as exc:
        raise SQLPolicyError("The generated SQL could not be parsed safely. Try rephrasing your question.") from exc

    if len(statements) != 1:
        raise SQLPolicyError("Only one read-only SELECT statement may be run at a time.")

    statement = statements[0]
    if type(statement).__name__ not in {"Select", "Union", "Intersect", "Except"}:
        raise SQLPolicyError("Only read-only SELECT queries are allowed.")

    forbidden_nodes = {
        "Alter", "Attach", "Command", "Create", "Delete", "Detach", "Drop", "Insert",
        "Merge", "Pragma", "TruncateTable", "Update", "Use",
    }
    if any(type(node).__name__ in forbidden_nodes for node in statement.walk()):
        raise SQLPolicyError("This query contains a database operation that is not allowed.")

    for function in statement.find_all(exp.Func):
        function_name = (
            function.name.lower()
            if isinstance(function, exp.Anonymous)
            else function.sql_name().lower()
        )
        if function_name not in ALLOWED_FUNCTIONS:
            raise SQLPolicyError(f"The SQL function '{function_name}' is not allowed.")

    cte_names = {
        cte.alias_or_name.lower()
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }
    for table in statement.find_all(exp.Table):
        table_name = table.name.lower()
        if table.db or table.catalog:
            raise SQLPolicyError("Database-qualified table references are not allowed.")
        if table_name not in ALLOWED_TABLES and table_name not in cte_names:
            raise SQLPolicyError(f"Queries may only use approved InsightSQL tables; '{table.name}' is not available.")

    for select in statement.find_all(exp.Select):
        for star in select.find_all(exp.Star):
            if not isinstance(star.parent, exp.Count):
                raise SQLPolicyError("Select named columns instead of returning every column.")
        if _contains_direct_identifier(select):
            raise SQLPolicyError(
                "Direct employee identifiers and personal details cannot be returned. Use aggregate results instead."
            )

    return candidate.rstrip(";").strip()


def prepare_sql(sql: str) -> tuple[str, dict[str, object]]:
    approved_sql = validate_sql(sql)
    statement = sqlglot.parse_one(approved_sql, read="sqlite")
    if any(isinstance(node, exp.Placeholder) for node in statement.walk()):
        raise SQLPolicyError("The assistant must not provide SQL parameters directly.")

    parameters: dict[str, object] = {}
    for index, literal in enumerate(statement.find_all(exp.Literal)):
        if literal.is_string:
            value: object = literal.this
        else:
            try:
                value = float(literal.this) if any(char in literal.this.lower() for char in (".", "e")) else int(literal.this)
            except ValueError as exc:
                raise SQLPolicyError("The query contains a numeric value SQLite cannot safely bind.") from exc
        parameter_name = f"p{index}"
        parameters[parameter_name] = value
        literal.replace(exp.Placeholder(this=parameter_name))

    return statement.sql(dialect="sqlite"), parameters
class InsightSQLError(Exception):
    """Base class for errors safe to summarize to an application user."""


class ConfigurationError(InsightSQLError):
    """Raised when required application configuration is missing or invalid."""


class SQLPolicyError(InsightSQLError):
    """Raised when a generated query violates the read-only SQL policy."""


class QueryExecutionError(InsightSQLError):
    """Raised when SQLite cannot safely execute an approved query."""


class QueryLimitError(InsightSQLError):
    """Raised when a query exceeds the configured result or execution limit."""


class ModelServiceError(InsightSQLError):
    """Raised when the model request or response cannot be used."""
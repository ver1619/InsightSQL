from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from insightsql.errors import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    openai_api_key: str | None
    openai_model: str
    auth_required: bool
    allowed_emails: frozenset[str]
    max_rows: int = 500
    query_timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls) -> Settings:
        raw_path = Path(os.getenv("INSIGHTSQL_DB_PATH", "data/insightsql.db")).expanduser()
        database_path = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
        environment = os.getenv("INSIGHTSQL_ENV", "development").strip().lower()
        auth_value = os.getenv("INSIGHTSQL_AUTH_REQUIRED")
        auth_required = (
            auth_value.strip().lower() in {"1", "true", "yes"}
            if auth_value is not None
            else environment == "production"
        )
        allowed_emails = frozenset(
            email.strip().lower()
            for email in os.getenv("INSIGHTSQL_ALLOWED_EMAILS", "").split(",")
            if email.strip()
        )
        if auth_required and not allowed_emails:
            raise ConfigurationError(
                "Set INSIGHTSQL_ALLOWED_EMAILS when authentication is required."
            )

        try:
            max_rows = int(os.getenv("INSIGHTSQL_MAX_ROWS", "500"))
            timeout_seconds = float(os.getenv("INSIGHTSQL_QUERY_TIMEOUT_SECONDS", "5"))
        except ValueError as exc:
            raise ConfigurationError("Query limits must be numeric values.") from exc
        if not 1 <= max_rows <= 5000 or not 0.1 <= timeout_seconds <= 60:
            raise ConfigurationError("Configured query limits are outside the supported range.")

        return cls(
            database_path=database_path,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
            auth_required=auth_required,
            allowed_emails=allowed_emails,
            max_rows=max_rows,
            query_timeout_seconds=timeout_seconds,
        )
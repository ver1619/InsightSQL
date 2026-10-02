from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from insightsql.config import Settings
from insightsql.database import QueryResult, execute_readonly_query
from insightsql.errors import ConfigurationError, ModelServiceError
from insightsql.llm import GeneratedQuery, generate_query


@dataclass(frozen=True, slots=True)
class AssistantResponse:
    sql: str | None
    explanation: str | None
    clarification: str | None
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]


QueryGenerator = Callable[..., GeneratedQuery]


def process_question(
    question: str,
    settings: Settings,
    *,
    generator: QueryGenerator = generate_query,
    conversation_context: Sequence[dict[str, str]] = (),
) -> AssistantResponse:
    normalized_question = question.strip()
    if not normalized_question:
        raise ConfigurationError("Enter a question before asking InsightSQL.")
    if len(normalized_question) > 1000:
        raise ConfigurationError("Questions must be 1,000 characters or fewer.")
    if not settings.openai_api_key:
        raise ConfigurationError("AI query generation is not configured. Set OPENAI_API_KEY.")

    generated = generator(
        normalized_question,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        conversation_context=conversation_context,
    )
    if generated.clarification and not generated.sql:
        return AssistantResponse(None, None, generated.clarification, (), ())
    if not generated.sql:
        raise ModelServiceError("InsightSQL could not create a query. Try rephrasing your question.")

    result: QueryResult = execute_readonly_query(
        generated.sql,
        settings.database_path,
        max_rows=settings.max_rows,
        timeout_seconds=settings.query_timeout_seconds,
    )
    return AssistantResponse(
        sql=result.sql,
        explanation=generated.explanation,
        clarification=None,
        columns=result.columns,
        rows=result.rows,
    )
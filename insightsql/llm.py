from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Sequence

from openai import OpenAI

from insightsql.errors import ModelServiceError

LOGGER = logging.getLogger("insightsql.llm")
SCHEMA_CONTEXT = """SQLite tables and approved fields:
- departments(department_id, department_code, name, location)
- employees(employee_id, department_id, job_title, hire_date, employment_status)
- projects(project_id, department_id, project_code, name, start_date, end_date, status)
- employee_projects(employee_id, project_id, project_role, assigned_on, released_on, allocation_pct)

Do not select employee_id, manager_id, email, first_name, or last_name as output. Employee identifiers may
only be used inside COUNT aggregates or joins. Never use SELECT *. Use SQLite syntax and only these tables.
"""
SYSTEM_PROMPT = """You translate business questions into safe SQLite SELECT queries for workforce analytics.
Return exactly one JSON object with keys: sql, clarification, explanation. Put a single read-only SELECT
query in sql, or null when clarification is needed. Never include markdown fences. If the question is
ambiguous, ask one concise clarification and do not guess. Only query the supplied schema. Never modify
data, inspect SQLite metadata, or return direct employee identifiers or personal details. The explanation
must describe query intent or assumptions only; you do not see query results and must not claim findings.
The application validates every query independently; instructions here are not a security boundary.
"""


@dataclass(frozen=True, slots=True)
class GeneratedQuery:
    sql: str | None
    clarification: str | None
    explanation: str | None


def generate_query(
    question: str,
    *,
    api_key: str,
    model: str,
    conversation_context: Sequence[dict[str, str]] = (),
) -> GeneratedQuery:
    try:
        client = OpenAI(api_key=api_key, timeout=25.0, max_retries=1)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n" + SCHEMA_CONTEXT}
        ]
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in conversation_context
            if item.get("role") in {"user", "assistant"} and item.get("content")
        )
        messages.append({"role": "user", "content": question})
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The model returned an empty response.")
        payload = json.loads(content)
        sql = payload.get("sql")
        clarification = payload.get("clarification")
        explanation = payload.get("explanation")
        if sql is not None and not isinstance(sql, str):
            raise ValueError("The model returned a non-text SQL value.")
        return GeneratedQuery(
            sql=sql.strip() if sql else None,
            clarification=clarification.strip() if isinstance(clarification, str) and clarification.strip() else None,
            explanation=explanation.strip() if isinstance(explanation, str) and explanation.strip() else None,
        )
    except Exception as exc:
        LOGGER.warning("model_request_failed", extra={"error_type": type(exc).__name__})
        raise ModelServiceError(
            "InsightSQL could not get a response from the AI service. Check your connection and try again."
        ) from exc
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from io import StringIO

import pandas as pd
import streamlit as st

from insightsql.config import Settings
from insightsql.database import ensure_database
from insightsql.errors import InsightSQLError
from insightsql.logging_config import configure_logging
from insightsql.service import process_question

LOGGER = logging.getLogger("insightsql")
EXAMPLE_QUESTIONS = (
    "How many employees are in each department?",
    "Show active projects and their owning departments.",
    "What is the average project allocation by department?",
)


def _require_access(settings: Settings) -> bool:
    if not settings.auth_required:
        st.sidebar.warning("Local development mode: sign-in is disabled.")
        return True

    try:
        is_logged_in = st.user.is_logged_in
    except Exception:
        st.error("Organization sign-in is not configured. Contact your administrator.")
        st.stop()
        return False

    if not is_logged_in:
        st.title("InsightSQL")
        st.write("Sign in with your organization account to continue.")
        st.button("Sign in", on_click=st.login, type="primary")
        st.stop()
        return False

    email = str(st.user.get("email", "")).strip().lower()
    if not email or email not in settings.allowed_emails:
        st.error("Your account is not authorized to use InsightSQL.")
        st.stop()
        return False
    return True


def _append_history(
    question: str,
    *,
    status: str,
    sql: str | None = None,
    row_count: int = 0,
    message: str | None = None,
) -> None:
    st.session_state.history.insert(
        0,
        {
            "question": question,
            "status": status,
            "sql": sql,
            "row_count": row_count,
            "message": message,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
    )
    del st.session_state.history[50:]


def _render_history() -> None:
    with st.sidebar:
        st.subheader("Query history")
        history = st.session_state.history
        if history and st.button("Clear history", use_container_width=True):
            st.session_state.history = []
            st.rerun()

        if not history:
            st.caption("Questions from this session will appear here.")
            return

        for index, item in enumerate(history):
            label = item["question"]
            if len(label) > 48:
                label = label[:45] + "..."
            with st.expander(label):
                st.caption(f"{item['created_at']} · {item['status']} · {item['row_count']} rows")
                if item["sql"]:
                    st.code(item["sql"], language="sql")
                if item["message"]:
                    st.caption(item["message"])
                if st.button("Use question", key=f"history-{index}"):
                    st.session_state.question_input = item["question"]
                    st.rerun()


def _render_response() -> None:
    response = st.session_state.get("active_response")
    if response is None:
        return

    if response.clarification:
        st.info(response.clarification)
        return

    if response.explanation:
        st.caption(f"Query interpretation: {response.explanation}")

    frame = pd.DataFrame(response.rows, columns=response.columns)
    st.caption(f"{len(frame):,} row(s) returned")
    st.dataframe(frame, use_container_width=True, hide_index=True)

    csv_buffer = StringIO()
    frame.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download CSV",
        data=csv_buffer.getvalue(),
        file_name="insightsql-results.csv",
        mime="text/csv",
    )

    numeric_columns = frame.select_dtypes(include="number").columns.tolist()
    category_columns = frame.select_dtypes(exclude="number").columns.tolist()
    if numeric_columns and category_columns and len(frame) > 1:
        chart_data = frame.set_index(category_columns[0])[numeric_columns]
        st.bar_chart(chart_data)

    if response.sql:
        with st.expander("Generated SQL"):
            st.code(response.sql, language="sql")


def main() -> None:
    st.set_page_config(page_title="InsightSQL", page_icon="IS", layout="wide")
    configure_logging()
    st.session_state.setdefault("history", [])
    try:
        settings = Settings.from_environment()
    except InsightSQLError as exc:
        st.error(f"InsightSQL configuration error: {exc}")
        return

    if not _require_access(settings):
        return

    try:
        ensure_database(settings.database_path)
    except (OSError, sqlite3.DatabaseError, InsightSQLError) as exc:
        st.error(f"InsightSQL could not open its SQLite database: {exc}")
        st.caption("Check INSIGHTSQL_DB_PATH and initialize the database as described in README.md.")
        return

    st.title("InsightSQL")
    st.caption("Ask a workforce data question in plain English.")
    _render_history()

    columns = st.columns(len(EXAMPLE_QUESTIONS))
    for column, example in zip(columns, EXAMPLE_QUESTIONS, strict=True):
        if column.button(example, use_container_width=True):
            st.session_state.question_input = example

    with st.form("question-form"):
        st.text_area(
            "Your question",
            key="question_input",
            height=110,
            max_chars=1000,
            placeholder="For example: How many active employees are in each department?",
        )
        submitted = st.form_submit_button("Ask InsightSQL", type="primary")

    if submitted:
        question = st.session_state.question_input.strip()
        if not question:
            st.warning("Enter a question to get started.")
        elif not settings.openai_api_key:
            message = "AI query generation is not configured. Set OPENAI_API_KEY in the application environment."
            st.error(message)
            _append_history(question, status="not run", message=message)
        else:
            request_id = uuid.uuid4().hex
            st.session_state.active_response = None
            try:
                conversation_context: list[dict[str, str]] = []
                for entry in reversed(st.session_state.history[:6]):
                    if entry["status"] == "complete" and entry["sql"]:
                        conversation_context.extend(
                            [
                                {"role": "user", "content": entry["question"]},
                                {"role": "assistant", "content": f"Previously approved query: {entry['sql']}"},
                            ]
                        )
                with st.spinner("Understanding your question and checking the query..."):
                    response = process_question(
                        question,
                        settings,
                        conversation_context=conversation_context,
                    )
                st.session_state.active_response = response
                _append_history(
                    question,
                    status="clarification" if response.clarification else "complete",
                    sql=response.sql,
                    row_count=len(response.rows),
                    message=response.clarification,
                )
                LOGGER.info(
                    "query_completed",
                    extra={"request_id": request_id, "row_count": len(response.rows)},
                )
            except InsightSQLError as exc:
                _append_history(question, status="rejected", message=str(exc))
                LOGGER.warning(
                    "query_rejected",
                    extra={"request_id": request_id, "error_type": type(exc).__name__},
                )
                st.error(str(exc))
            except Exception:
                _append_history(
                    question,
                    status="failed",
                    message=f"Reference: {request_id}",
                )
                LOGGER.exception("query_failed", extra={"request_id": request_id})
                st.error(f"InsightSQL could not complete that request. Reference: {request_id}")

    _render_response()


if __name__ == "__main__":
    main()
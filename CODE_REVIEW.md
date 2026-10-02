# Code Review: InsightSQL

## Findings

### [P1] Authenticated users are not authorized by role or data scope

[app.py](app.py#L26) only checks whether the signed-in email appears in a static allowlist configured by [config.py](insightsql/config.py#L33). The user identity or department scope is not passed to the query service or repository, so every allowlisted user can query the same workforce data. This does not meet the PRD's role-based access-control requirement ([PRD.md](PRD.md#L99)).

**Improve:** Define roles and row/column scopes, bind the authenticated subject and scope to each request, and enforce them in the query policy/repository rather than relying on model instructions. Add tests proving one user's query cannot return another department's records.

### [P1] Read-only queries can disclose individual-level workforce attributes

The SQL policy blocks direct employee identifiers in projections ([sql_policy.py](insightsql/sql_policy.py#L23)), but the SQLite authorizer permits row-level `job_title`, `hire_date`, `employment_status`, and `department_id` reads ([database.py](insightsql/database.py#L17)). A query such as `SELECT job_title, hire_date, employment_status, department_id FROM employees` is read-only and passes these controls. Grouped counts can also expose very small cohorts. Omitting names and email does not prevent re-identification from these attributes.

**Improve:** Make employee analytics aggregate-only by default, suppress groups below an approved minimum cohort size, and prevent differencing through repeated filters. Treat permitted dimensions and metrics as governed semantic definitions. Add regression tests for row-level output and small-group aggregates.

### [P1] Required auditability is only session-scoped

Query history is stored in `st.session_state` ([app.py](app.py#L53)) and disappears with the session. Application logs record completion or rejection, but omit the authenticated subject and query/scope audit record; database events also lack a request ID ([app.py](app.py#L212), [database.py](insightsql/database.py#L133)). This falls short of the PRD's query auditing requirement ([PRD.md](PRD.md#L104)) and the system design's separation of audit events from debug logs ([SYSTEM_DESIGN.md](SYSTEM_DESIGN.md#L165)).

**Improve:** Add a durable, access-controlled audit sink separate from the analytics database. Record subject, authorization scope, timestamp, request ID, normalized or hashed SQL, decision, result row count, and failure category. Do not store raw result rows or secrets. Define retention and access policies.

### [P2] Request correlation and latency are not end-to-end

A request ID is created in the Streamlit callback, but it is not propagated through `process_question`, the OpenAI adapter, or SQLite execution. The model and repository log events without it ([llm.py](insightsql/llm.py#L78), [database.py](insightsql/database.py#L133)). The logs also omit operation duration, despite the system design requiring correlation IDs and durations ([SYSTEM_DESIGN.md](SYSTEM_DESIGN.md#L165)). Failures spanning these layers will be difficult to diagnose.

**Improve:** Pass a request context through service, model, and database boundaries; consistently include its ID, operation, duration, outcome, and sanitized error category in structured logs. Add tests that assert correlation survives both success and failure paths.

### [P2] Streamlit entry point owns too many responsibilities

[app.py](app.py) combines authentication, configuration loading, database initialization, session history, conversational context, result shaping, CSV export, chart selection, orchestration, and error presentation. This makes UI reruns and behavior changes harder to test independently, contrary to the system design's thin-presentation boundary ([SYSTEM_DESIGN.md](SYSTEM_DESIGN.md#L148)).

**Improve:** Move authentication and request/history coordination into small application services, and move response/history rendering into presentation modules. Keep `app.py` focused on wiring Streamlit widgets to those interfaces; add focused tests for authorization and UI state transitions.

### [P2] The renamed `.env` file is not loaded by the application

The README previously referred to `.env.example`; that file has been renamed to `.env`. The `.env` entry is ignored by Git ([.gitignore](.gitignore#L1)), but [config.py](insightsql/config.py#L21) reads `os.environ` directly and does not load values from the file. Developers may believe credentials and settings in `.env` are active when they are not. The `.env` contents were not inspected because the file may contain secrets.

**Improve:** Keep the README explicit that settings must be exported to the process environment, or add a `.env` loader with process-environment precedence and document it. Keep `.env` ignored and never commit its contents.

## Review Summary

The SELECT-only boundary is reasonably layered: SQLGlot AST validation is followed by SQLite read-only mode, `query_only`, a read authorizer, execution timeout, and row cap. The main production risks are authorization scope and workforce-data privacy; read-only access alone does not make a query safe to disclose. Durable audit and end-to-end observability should also be addressed before production use.

## Validation and Scope

This review is based on the current workspace contents and the PRD/system-design requirements. The workspace has no Git metadata, so review findings compare current code to those documents rather than to a change set. `.env` is ignored and was deliberately not opened.

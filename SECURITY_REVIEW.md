# InsightSQL Application Security Review

**Review date:** 2026-10-02  
**Scope:** Streamlit application, OpenAI integration, SQL policy, SQLite access, configuration, and logging.  
**Classification:** High = confidentiality/integrity risk that should block production; Medium = meaningful residual risk requiring mitigation; Low = hygiene or defense-in-depth improvement.

## Executive Summary

The application has a useful read-only execution boundary: SQLGlot parses generated SQL, SQLite opens the database read-only, query-only mode and an authorizer limit database operations, SQL literals are bound, and queries have time and row limits. No direct SQL injection path was identified in the reviewed flow.

The application is not ready for production workforce data. Allowlisted users are not separated by role or data scope, and approved queries can return employee-level quasi-identifiers or expose small cohorts. The local SQLite file has no application-level at-rest encryption, and durable access auditing is not implemented. Prompt instructions do not replace these missing authorization and privacy controls.

## Findings

### SEC-01 — High: Authenticated users share unrestricted data scope

**Category:** Data leakage / Authorization

Production authentication checks a signed-in email against a static allowlist ([app.py](app.py#L26), [config.py](insightsql/config.py#L33)). Once admitted, the user's identity and department/role scope are not passed into `process_question` or `execute_readonly_query`. All allowlisted users can query the same approved tables and columns. This does not meet the PRD's role-based access-control requirement ([PRD.md](PRD.md#L99)).

**Mitigations:**

- Define roles and row/column entitlements, including who may access employee, project, and department data.
- Bind the authenticated subject and authorized scope to every query request; enforce scope in the repository or a trusted semantic-query layer, not in the prompt.
- Fail closed if identity or scope resolution is unavailable.
- Add tests proving users in different scopes cannot query or infer each other's records.

### SEC-02 — High: Read-only queries can return re-identifiable employee records

**Category:** Data leakage / Privacy

The policy rejects direct identifiers in projections ([sql_policy.py](insightsql/sql_policy.py#L23)), but the database allowlist still exposes `job_title`, `hire_date`, `employment_status`, and `department_id` at employee-row granularity ([database.py](insightsql/database.py#L17)). A query selecting those fields from `employees` is a valid `SELECT` and can return one row per employee. Small grouped counts and repeated filters can also reveal sensitive workforce facts. Removing names and emails alone does not prevent re-identification.

**Mitigations:**

- Default employee analytics to aggregates and deny employee-grain results unless a specifically authorized role requires them.
- Suppress groups below a privacy threshold and prevent differencing attacks across related queries.
- Limit sensitive dimensions such as employment status and hire date to approved metrics and use cases.
- Add security tests for row-level queries, singleton groups, rare categories, and repeated-filter inference.

### SEC-03 — High: SQLite data at rest is not encrypted by the application

**Category:** Credential/data exposure

Analytics queries use SQLite's read-only URI and access controls, but these controls do not encrypt the database file. The default database path is a local file, and `.gitignore` only excludes local artifacts from ordinary Git adds; it does not encrypt the database or backups, nor does it prove that a file was never committed ([config.py](insightsql/config.py#L21), [.gitignore](.gitignore#L1)). Workforce data may therefore be exposed through filesystem access, copied backups, or host compromise.

**Mitigations:**

- Require encrypted volumes with managed keys for the database, WAL/SHM files, and backups; consider an approved encrypted SQLite solution if volume encryption is insufficient.
- Restrict file and backup permissions to the application identity and define backup retention/deletion.
- Verify repository history and deployment artifact handling before loading production data. Do not treat `.gitignore` as a security boundary.

### SEC-04 — Medium: Prompt injection can steer queries within the broad data allowlist

**Category:** Prompt injection / Data leakage

The system prompt tells GPT to return a safe query, but the question and prior conversation context are untrusted input. The SQL validator is an effective capability boundary against writes and unapproved tables, but it does not decide whether a permitted workforce query is appropriate for the current user or sufficiently aggregated. A prompt injection can therefore request broad or sensitive read-only results within the current allowlist. No database rows are included in the model context, which reduces indirect prompt-injection exposure but does not address this query-selection risk ([llm.py](insightsql/llm.py#L17), [app.py](app.py#L192)).

**Mitigations:**

- Treat all user text and conversation history as untrusted; keep security policy outside the model prompt.
- Apply SEC-01 authorization scopes and SEC-02 privacy rules after generation and before execution.
- Prefer a semantic layer of approved metrics/dimensions over arbitrary SQL where practical.
- Retain tests for prompt-injection strings, role/scope bypass attempts, and requests for employee-grain data.

### SEC-05 — Medium: SELECT-only validation does not fully bound query resource cost

**Category:** Unsafe queries / Availability

The policy restricts statement type, table names, and functions, while execution applies a timeout and result-row cap ([sql_policy.py](insightsql/sql_policy.py#L41), [database.py](insightsql/database.py#L100)). A small result can still require an expensive cross join, deeply nested subqueries, or high-cardinality aggregation before SQLite can return it. Repeated requests can also consume OpenAI quota and tie up the Streamlit worker; there is no per-user request rate or concurrency limit.

**Mitigations:**

- Bound joins, nesting depth, and query-plan complexity; reject cross joins and unbounded recursive constructs unless explicitly required.
- Add per-user request throttling, concurrent-query limits, and model-call budgets.
- Keep the progress-handler timeout and row cap, and test adversarial query plans against production-sized synthetic data.

### SEC-06 — Medium: Security events are not durably attributable or correlated

**Category:** Logging / Auditability

Query history is session-scoped, and logs omit the user identity, authorization scope, normalized query, and durable audit decision. The request ID created by the UI is not propagated into OpenAI or SQLite events. This limits incident investigation and does not satisfy the PRD's query-audit requirement ([app.py](app.py#L53), [app.py](app.py#L186), [database.py](insightsql/database.py#L133), [PRD.md](PRD.md#L104)). Current logs do avoid recording raw questions and result rows, which is a useful privacy control.

**Mitigations:**

- Create a protected audit sink separate from the analytics database, with a documented retention policy.
- Record subject, scope, timestamp, request ID, normalized or hashed SQL, allow/reject outcome, row count, duration, and sanitized error category; never record raw results or secrets.
- Propagate one correlation ID through UI, service, model, and database layers, with restricted access to diagnostics.

### SEC-07 — Medium: `.env` is ignored but not loaded, and its contents were not assessed

**Category:** Credential exposure / Configuration

`.gitignore` excludes `.env` ([.gitignore](.gitignore#L1)), but configuration reads process environment variables directly and does not parse the renamed `.env` file ([config.py](insightsql/config.py#L21)). The README has been updated to explain this behavior ([README.md](README.md#L24)). If credentials are stored only in `.env`, the app will not use them; conversely, ignore rules do not prove the file is absent from existing repository history. The `.env` contents were not opened or scanned during this review.

**Mitigations:**

- Keep `.env` local and ignored; use process environment or a deployment secret manager for production credentials.
- If local `.env` loading is desired, add an explicit loader with process-environment precedence and keep the file out of logs, artifacts, and source control.
- Rotate any credential that may have been committed or exposed, and scan repository history and deployment artifacts using approved secret-scanning tooling.
- Do not paste API keys into chat, logs, or review documents.

## Control Assessment

- **SQL injection:** No direct injection issue was identified in the reviewed execution path. Model SQL is parsed; string/numeric literals are converted to SQLite named parameters; execution uses `sqlite3` parameter binding plus read-only mode and an authorizer. Continue treating generated SQL as untrusted and preserve these independent controls.
- **Unsafe writes:** The validator rejects non-`SELECT` statements and multiple statements, and SQLite independently blocks writes. Keep negative tests for `DROP`, `DELETE`, `UPDATE`, `ALTER`, `TRUNCATE`, and `INSERT` at both validator and execution boundaries.
- **Credential handling:** The OpenAI key is obtained from configuration and passed to the OpenAI client; reviewed logging statements do not intentionally log it. The `.env` file itself was not inspected, and Git history could not be assessed because this workspace has no Git metadata.
- **Data sent to OpenAI:** The integration sends the user's question, fixed schema context, and limited conversation history; it does not send database result rows. Questions and history may still contain personal information, so establish provider retention settings and user-facing privacy notices before production deployment.

## Production Readiness

Do not load real workforce data until SEC-01 through SEC-03 are addressed. Before launch, also implement durable auditing and request correlation, add rate/resource controls, review OpenAI data-retention settings, and run security tests with synthetic data. This is a source review, not a penetration test or a scan of `.env`, Git history, dependency vulnerabilities, or deployed infrastructure.

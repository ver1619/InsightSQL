# InsightSQL Production Readiness Assessment

**Assessment date:** 2026-10-02  
**Overall score:** **44/100**  
**Decision:** **No-go for production use with real employee data.** Suitable for a synthetic-data demo or a restricted technical evaluation until the blockers below are resolved.

This assessment considers the current application, product requirements, system/database designs, and review documents. It is based on repository contents and a test run; it does not certify a deployment environment, identity provider, OpenAI account configuration, or operational controls.

## Scorecard

| Area                         |      Score | Assessment                                                                                                                                                                           |
| ---------------------------- | ---------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Product readiness            |      10/15 | Clear use case and usable query workflow, but the documented workforce questions exceed the data model and results do not provide a dependable business-metric summary.              |
| Architecture                 |       8/15 | Application services and SQL/database controls are separated, but the UI remains a broad orchestration surface and the deployment design is limited to a single local app/database.  |
| Database and data operations |       7/15 | Relational schema has primary/foreign keys, checks, and indexes; schema versioning, backups, restore procedures, encryption, and production data lifecycle are missing.              |
| QA                           |      10/15 | Fresh run passes 30 tests covering SQL policy, SQLite, service behavior, and a Streamlit smoke test; provider, load, deployment, and full authorization scenarios remain unverified. |
| Security and privacy         |       4/20 | Read-only SQL defenses are a meaningful baseline, but role/row authorization, aggregate privacy, durable audit, and data-at-rest protection are production blockers.                 |
| DevOps and operations        |       5/20 | Local setup is documented, but there is no visible CI/CD, deployment manifest, monitoring/alerting setup, backup automation, or incident/restore runbook.                            |
| **Total**                    | **44/100** | **Preproduction MVP**                                                                                                                                                                |

## Strengths

- Product requirements, architecture, database design, code review, and security review are documented and cross-reference one another.
- The application has a clear user workflow: natural-language questions, clarification, generated SQL visibility, tabular results, CSV export, and session-scoped history.
- SQL is parsed with SQLGlot, restricted to a single `SELECT`, table/function allowlists, and bound literals. SQLite adds read-only mode, query-only mode, an authorizer, a query timeout, and a result-row cap ([sql_policy.py](insightsql/sql_policy.py), [database.py](insightsql/database.py)).
- Database records are not sent to OpenAI; the model receives the question, schema context, and limited conversation context ([llm.py](insightsql/llm.py)).
- Schema constraints and synthetic sample data support local testing without production records ([database_schema.sql](database_schema.sql)).
- The test suite passed **30 tests** during this assessment, including SQL rejection, SQLite read-only behavior, result limits, service behavior, and a Streamlit smoke test.
- Setup instructions explain that `.env` is ignored but not loaded by the application and advise using process environment variables ([README.md](README.md)).

## Weaknesses

- **Authorization is not data scoping.** Production sign-in uses an email allowlist; there are no roles, department scopes, or row-level restrictions. Authorized users can query the same dataset.
- **Employee privacy protection is incomplete.** The query path can return employee-grain quasi-identifiers, and aggregate queries do not enforce minimum cohort sizes or prevent differencing.
- **The PRD exceeds the current schema.** The database contains departments, employees, projects, and assignments, but lacks the region, overtime, performance, attendance/absence, and departure-history facts required for several stated workforce questions. Attrition cannot be reliably calculated from current fields.
- **Results are not yet decision-grade.** The interface shows result rows and a model-supplied query interpretation, but does not independently summarize computed findings, expose metric definitions, or provide calibrated confidence/validation evidence.
- **No durable audit trail is implemented.** Query history is held in Streamlit session state; logs are not a protected audit record with user, scope, query decision, and retention.
- **SQLite operations are local and single-instance.** No application-level encryption, schema migration/versioning, backup/restore process, or concurrency/load acceptance criteria are present.
- **Operational delivery is incomplete.** No visible CI workflow, pinned dependency lock, image/build definition, deployment configuration, SLO/monitoring, or alerting is included in the repository.
- **Test breadth is limited.** The suite does not establish authorization isolation, privacy thresholds, real OpenAI contract behavior, production identity configuration, concurrent request behavior, backup recovery, or workload capacity. Tests mock/stub model behavior and do not call OpenAI.

## Key Risks

| Risk                                                                           | Likelihood | Impact   | Current exposure                                                                  |
| ------------------------------------------------------------------------------ | ---------- | -------- | --------------------------------------------------------------------------------- |
| A user can query data outside their business role or department                | High       | Critical | Email allowlisting authenticates access but does not scope queries.               |
| Workforce facts can be re-identified from row-level attributes or small groups | High       | Critical | Read-only access prevents writes, not inference or disclosure.                    |
| A lost/copied database or backup exposes workforce data                        | Medium     | High     | SQLite is a plaintext local file unless the host/storage layer encrypts it.       |
| AI-generated SQL is syntactically valid but semantically wrong                 | Medium     | High     | No independent metric catalog, answer verification, or approval workflow.         |
| Expensive/repeated questions consume application capacity or model budget      | Medium     | High     | Timeout and row caps exist; per-user rate, concurrency, and cost controls do not. |
| Production incident cannot be reconstructed reliably                           | Medium     | High     | Session history is ephemeral and logs lack durable, end-to-end audit context.     |
| Product promises do not match available data                                   | High       | Medium   | Several PRD example metrics cannot be calculated from the current schema.         |
| SQLite contention or local disk failure interrupts service/data availability   | Medium     | High     | No production backup, restore, or multi-instance strategy is provided.            |

## Recommended Improvements

### P0: Required Before Real Workforce Data

1. **Implement authorization scopes.** Define roles and department/row access policy; propagate the authenticated subject and scope through the service; enforce scope in trusted query/data code. Test cross-department denial and fail-closed behavior.
2. **Establish a workforce privacy policy.** Default to aggregates, restrict sensitive dimensions, suppress small cohorts, and prevent differencing across repeated queries. Add adversarial tests for row-level and sparse-group disclosures.
3. **Align product scope and data model.** Either narrow the first release to metrics the current schema can support or add governed source data for region, attrition, overtime, performance, and attendance. Define business metric formulas and ownership before exposing them to users.
4. **Protect stored data.** Require encrypted storage and backups, restrict filesystem permissions, and document key ownership, retention, recovery, and deletion. Do not treat `.gitignore` as encryption or proof that secrets were never committed.
5. **Add durable audit and incident evidence.** Record authenticated subject, scope, request ID, normalized/hashed SQL, allow/reject outcome, row count, duration, and sanitized error in a protected audit sink with defined retention. Exclude API keys and raw result rows.

### P1: Required Before Broad Internal Rollout

1. **Create automated delivery gates.** Add CI for pytest, formatting/lint, type checks, dependency vulnerability scanning, and secret scanning. Generate a locked, reproducible dependency set and publish build artifacts from a controlled pipeline.
2. **Prove operational reliability.** Add schema migrations/version checks, automated encrypted backups, restore drills, health/readiness checks, and a documented incident/on-call runbook. Define availability, latency, recovery-point, and recovery-time targets.
3. **Set workload and cost limits.** Add per-user rate limits, concurrency control, OpenAI token/cost budgets, and SQL complexity limits (for example, join count, nesting depth, and cross-join policy). Load-test against representative data volumes.
4. **Improve model/answer quality controls.** Introduce a semantic metric catalog and query fixtures for canonical questions. Clearly separate query interpretation from findings derived from actual result rows, and measure accuracy against reviewed expected results.
5. **Verify production identity and transport.** Validate OIDC configuration, authorization failure paths, HTTPS termination, secret rotation, and deployment isolation in a staging environment with synthetic data.

### P2: Operational Maturity

1. Add structured end-to-end request correlation and latency/error metrics across UI, OpenAI, SQL validation, and SQLite.
2. Add data retention and user-visible privacy notices for questions sent to OpenAI; verify the organization's provider retention and contractual settings.
3. Add accessibility, browser/device, and user-acceptance testing with representative HR, operations, and executive users.
4. Reassess SQLite if multiple application replicas, substantial concurrent writes, high availability, or larger analytics workloads become requirements; plan a client-server database migration behind the repository interface.

## Release Gates

Do not approve production workforce data until all of the following are true:

- Role/department authorization and small-cohort privacy tests pass.
- Approved product metrics are represented by governed, validated data and definitions.
- Encrypted storage, tested backups/restores, and durable audit are operational.
- CI security/quality gates and staging deployment tests are passing.
- OpenAI data handling, incident response, and production ownership are approved.

## Assessment Evidence and Limits

- `python -m pytest -q`: **30 passed** on 2026-10-02.
- Reviewed [PRD.md](PRD.md), [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md), [DATABASE_DESIGN.md](DATABASE_DESIGN.md), [database_schema.sql](database_schema.sql), [README.md](README.md), [CODE_REVIEW.md](CODE_REVIEW.md), and [SECURITY_REVIEW.md](SECURITY_REVIEW.md).
- No Git metadata was available in the workspace. `.env` contents, repository history, dependency vulnerability state, OpenAI account configuration, and any deployed infrastructure were not inspected or penetration-tested.

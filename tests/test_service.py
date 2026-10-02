from insightsql.config import Settings
from insightsql.llm import GeneratedQuery
from insightsql.service import process_question


def test_process_question_executes_generated_select(tmp_path) -> None:
    database_path = tmp_path / "insightsql.db"
    settings = Settings(
        database_path=database_path,
        openai_api_key="test-key",
        openai_model="test-model",
        auth_required=False,
        allowed_emails=frozenset(),
    )
    from insightsql.database import initialize_database

    initialize_database(database_path, include_seed=True)
    response = process_question(
        "How many employees are there?",
        settings,
        generator=lambda question, **kwargs: GeneratedQuery(
            sql="SELECT COUNT(employee_id) AS headcount FROM employees",
            clarification=None,
            explanation="This is the total number of employees.",
        ),
    )
    assert response.rows == ((20,),)
    assert response.columns == ("headcount",)


def test_process_question_returns_clarification_without_running_sql(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "missing.db",
        openai_api_key="test-key",
        openai_model="test-model",
        auth_required=False,
        allowed_emails=frozenset(),
    )
    response = process_question(
        "Show performance",
        settings,
        generator=lambda question, **kwargs: GeneratedQuery(
            sql=None,
            clarification="Which period do you mean?",
            explanation=None,
        ),
    )
    assert response.clarification == "Which period do you mean?"
    assert response.rows == ()


def test_process_question_passes_conversation_context_to_generator(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "missing.db",
        openai_api_key="test-key",
        openai_model="test-model",
        auth_required=False,
        allowed_emails=frozenset(),
    )
    context = [
        {"role": "user", "content": "How many employees are active?"},
        {"role": "assistant", "content": "Previously approved query: SELECT COUNT(employee_id) FROM employees"},
    ]
    received_context = []

    def generator(question, **kwargs):
        received_context.extend(kwargs["conversation_context"])
        return GeneratedQuery(sql=None, clarification="Which department?", explanation=None)

    response = process_question(
        "How many are in Sales?",
        settings,
        generator=generator,
        conversation_context=context,
    )

    assert response.clarification == "Which department?"
    assert received_context == context
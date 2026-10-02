from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_app_renders_without_openai_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INSIGHTSQL_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    app = AppTest.from_file(str(APP_PATH)).run(timeout=15)

    assert not app.exception
    assert app.title[0].value == "InsightSQL"
    assert app.text_area[0].label == "Your question"
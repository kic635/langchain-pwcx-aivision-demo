"""Exercise the two conversation panels against the real context server."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_two_conversations_and_recall_toggle(monkeypatch):
    monkeypatch.setenv("MODEL_MODE", "fixture")
    monkeypatch.setenv("AIVISION_ENABLED", "false")
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    app.run(timeout=30)
    assert not app.exception
    app.button[1].click().run(timeout=30)
    assert not app.exception
    app.button[2].click().run(timeout=30)
    assert not app.exception
    assert int(app.metric[0].value) >= 1
    assert "12 月 18 日" in app.session_state["B"]["answer"]
    app.checkbox[0].uncheck().run()
    app.button[2].click().run(timeout=30)
    assert not app.exception
    assert int(app.metric[0].value) == 0

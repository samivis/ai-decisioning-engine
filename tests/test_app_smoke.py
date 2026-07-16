"""Streamlit smoke test: the app boots, renders, and can run a decision."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def test_app_boots_and_decides():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value.startswith("Explainable credit decisioning")

    # The seeded dispute decision is selectable on a cold start.
    dispute_select = at.selectbox[1]
    assert "D-SEED-LASTWEEK" in dispute_select.options

    # Run a decision for the default persona via the form submit.
    submits = [b for b in at.button if b.label == "Run decision"]
    assert len(submits) == 1
    submits[0].click().run()
    assert not at.exception

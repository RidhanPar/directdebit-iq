"""Runtime smoke tests for the deployed Streamlit entry point."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_entrypoint_renders_without_exception() -> None:
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=60).run()

    assert not app.exception

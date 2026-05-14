from pathlib import Path

from streamlit.testing.v1 import AppTest

from manim_skill.frontend import backend as backend_mod
from manim_skill.frontend.payload import ConceptCard

_APP_PATH = str(
    Path(__file__).resolve().parents[2]
    / "manim_skill" / "frontend" / "app.py"
)

_CONCEPTS = [
    {"concept": "Attention", "why_suitable": "w", "storyboard": "s1"},
    {"concept": "MultiHead", "why_suitable": "w", "storyboard": "s2"},
]


class FakeBackendClient:
    """Configurable test double. Always returns terminal job statuses
    so the app's poll-and-sleep loop is never entered under AppTest."""

    def __init__(self, *, job_status="done"):
        self.job_status = job_status
        self.submitted_concepts = None
        self.submitted_analyze = None
        self.deleted = []

    def submit_analyze(self, content, kind, guide_prompt=None):
        self.submitted_analyze = (content, kind, guide_prompt)
        return "analyze-job"

    def submit_render_concepts(self, concepts):
        self.submitted_concepts = concepts
        return "render-job"

    def get_job(self, job_id):
        if job_id == "analyze-job":
            return {
                "status": "done",
                "result": {"concepts": _CONCEPTS},
            }
        return {"status": self.job_status, "error": "render boom"}

    def download_result_bytes(self, job_id):
        return b"PK\x03\x04fake-zip"

    def delete_job(self, job_id):
        self.deleted.append(job_id)


def _app_with_client(monkeypatch, client):
    monkeypatch.setattr(
        backend_mod, "get_backend_client", lambda: client
    )
    return AppTest.from_file(_APP_PATH)


def test_initial_run_is_upload_stage(monkeypatch):
    at = _app_with_client(monkeypatch, FakeBackendClient())
    at.run()
    assert not at.exception
    assert at.session_state["stage"] == "upload"


def test_upload_stage_has_uploader_and_analyze_button(monkeypatch):
    at = _app_with_client(monkeypatch, FakeBackendClient())
    at.run()
    assert len(at.file_uploader) == 1
    assert any(b.label == "分析" for b in at.button)


def test_reviewing_stage_shows_concept_cards(monkeypatch):
    at = _app_with_client(monkeypatch, FakeBackendClient())
    at.session_state["stage"] = "reviewing"
    at.session_state["cards"] = [
        ConceptCard("Attention", "w", "s1"),
        ConceptCard("MultiHead", "w", "s2"),
    ]
    at.run()
    assert not at.exception
    text_areas = [ta.value for ta in at.text_area]
    assert "s1" in text_areas and "s2" in text_areas
    assert any(b.label.startswith("開始渲染") for b in at.button)


def test_reviewing_start_render_submits_and_advances(monkeypatch):
    # Use job_status="failed" so the rendering stage stays put (doesn't
    # chain into "done") — AppTest re-runs st.rerun() immediately, so a
    # "done" render job would advance all the way to the done stage.
    client = FakeBackendClient(job_status="failed")
    at = _app_with_client(monkeypatch, client)
    at.session_state["stage"] = "reviewing"
    at.session_state["cards"] = [ConceptCard("Attention", "w", "s1")]
    at.run()
    render_btn = next(
        b for b in at.button if b.label.startswith("開始渲染")
    )
    render_btn.click().run()
    assert client.submitted_concepts == [
        {"concept": "Attention", "why_suitable": "w", "storyboard": "s1"}
    ]
    assert at.session_state["stage"] == "rendering"


def test_reviewing_over_quota_disables_render_button(monkeypatch):
    at = _app_with_client(monkeypatch, FakeBackendClient())
    at.session_state["stage"] = "reviewing"
    at.session_state["cards"] = [
        ConceptCard(f"C{i}", "w", f"s{i}") for i in range(6)
    ]
    at.run()
    render_btn = next(
        b for b in at.button if b.label.startswith("開始渲染")
    )
    assert render_btn.disabled is True
    assert len(at.warning) >= 1


def test_rendering_stage_advances_to_done_when_job_done(monkeypatch):
    at = _app_with_client(
        monkeypatch, FakeBackendClient(job_status="done")
    )
    at.session_state["stage"] = "rendering"
    at.session_state["render_job_id"] = "render-job"
    at.run()
    assert not at.exception
    assert at.session_state["stage"] == "done"


def test_rendering_stage_shows_error_when_job_failed(monkeypatch):
    at = _app_with_client(
        monkeypatch, FakeBackendClient(job_status="failed")
    )
    at.session_state["stage"] = "rendering"
    at.session_state["render_job_id"] = "render-job"
    at.run()
    assert at.session_state["stage"] == "rendering"
    assert len(at.error) >= 1


def test_done_stage_shows_download_button(monkeypatch):
    at = _app_with_client(monkeypatch, FakeBackendClient())
    at.session_state["stage"] = "done"
    at.session_state["render_job_id"] = "render-job"
    at.run()
    assert not at.exception
    # In Streamlit 1.57.0, st.download_button is not tracked by AppTest
    # as a first-class accessor; it appears via at.get("download_button").
    assert len(at.get("download_button")) == 1

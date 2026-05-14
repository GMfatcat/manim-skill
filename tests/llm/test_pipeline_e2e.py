import json
import zipfile

import pytest

from manim_skill.llm.client import FakeLLMClient
from manim_skill.llm.pipeline import run_pipeline
from manim_skill.render.jobs import JobStatus

_ANALYZE = (
    '{"concepts": [{"concept": "Greeting", "why_suitable": "simple", '
    '"storyboard": "Show a title card."}]}'
)
_SPEC = (
    '{"title": "Greeting", "beats": ['
    '{"component": "TextBeat", "params": {"text": "Hello"}, '
    '"duration": 1.0}]}'
)


@pytest.mark.docker
def test_run_pipeline_end_to_end_produces_zip(tmp_path):
    client = FakeLLMClient(responses=[_ANALYZE, _SPEC])
    batch = run_pipeline(
        client, "some source text", "text", tmp_path, repair=False
    )
    assert batch.status == JobStatus.DONE
    assert batch.zip_path is not None and batch.zip_path.exists()
    with zipfile.ZipFile(batch.zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert len(manifest["concepts"]) == 1
    assert manifest["concepts"][0]["status"] == "done"


@pytest.mark.docker
def test_run_pipeline_repair_loop_recovers_broken_raw_beat(tmp_path):
    # codegen produces a spec with a BROKEN raw beat (valid per schema,
    # since validation only checks that raw beats carry code); the
    # repair loop feeds the render error back to the LLM, which returns
    # working code.
    analyze = (
        '{"concepts": [{"concept": "Raw", "why_suitable": "w", '
        '"storyboard": "s"}]}'
    )
    broken_spec = (
        '{"title": "Raw", "beats": ['
        '{"component": "raw", "code": "this is not valid python !!!", '
        '"duration": 0.5}]}'
    )
    fixed_code = "self.wait(0.5)"
    client = FakeLLMClient(responses=[analyze, broken_spec, fixed_code])
    batch = run_pipeline(client, "text", "text", tmp_path, repair=True)

    assert batch.status == JobStatus.DONE
    clip = batch.clip_jobs[0]
    assert clip.status == JobStatus.DONE
    assert clip.beat_jobs[0].beat.code == "self.wait(0.5)"

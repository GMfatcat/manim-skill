# Plan 8: Streamlit 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Phase 2 的 Streamlit 前端——上傳素材、審核/編輯 LLM 找到的概念、提交渲染、下載 zip——透過 `BackendClient` 與後端溝通。

**Architecture:** Streamlit 是薄殼：純邏輯（概念卡片模型、配額、組 render payload）抽到 `frontend/payload.py` 獨立可測；`frontend/backend.py` 提供 `BackendClient` 工廠；`frontend/app.py` 是 Streamlit 腳本，用 `st.session_state` 跑一個 `upload → analyzing → reviewing → rendering → done` 的階段機，每個階段呼叫 `BackendClient`。前端不深測——純邏輯單元測試 + `streamlit.testing.AppTest` 輕量 smoke test；後端與 client 已在 Plan 6/7 測透。

**Tech Stack:** Python ≥3.12、Streamlit、`streamlit.testing.v1.AppTest`、既有的 `BackendClient`、pytest。

---

## 背景：Plan 6 + Plan 7（已合併入 `main`）可重用的部分

- `manim_skill/backend_client.py` — `BackendClient(base_url, *, http_client=None, timeout=120.0)` + `BackendClientError`。現有方法：`submit_render_spec(spec) -> str`、`submit_render_concepts(concepts) -> str`、`submit_analyze(content, kind, guide_prompt=None) -> str`、`get_job(job_id) -> dict`、`wait_for_job(...)`、`download_result(job_id, dest_path) -> Path`、`delete_job(job_id)`、`get_catalog() -> str`。內部 `self._client`（httpx.Client）、`self._base_url`、`self._request(method, path, **kwargs)`。
- 後端 API（Plan 6）：job 狀態 doc 形如 `{"job_id","type","status","progress","result","error"}`；`status` ∈ `"queued"/"running"/"done"/"failed"`；done 的 analyze job 的 `result` 是 `{"concepts": [{"concept","why_suitable","storyboard"}, ...]}`；done 的 render job 的 `result` 含 `zip_path`。配額：後端對 `mode=codegen` 的概念數 > `web_quota`（預設 5）回 400。
- `pyproject.toml`：`dependencies` 已含 `httpx>=0.27`（Plan 7 升為 runtime）；`[project.optional-dependencies] dev = ["pytest>=8.0", "fakeredis>=2.21"]`。
- 既有測試 `tests/test_backend_client.py` 用 `starlette.testclient.TestClient`（httpx.Client 子類）對 `create_app` + fakeredis 做 in-process 測試；`enqueue_*` 被 monkeypatch 成 no-op。輔助函式 `_backend(tmp_path, monkeypatch)` 回 `(BackendClient, JobStore)`。

環境：Windows + Docker Desktop（amd64），Python 3.13。

## 範圍界定

- **包含**：`BackendClient` 擴充（`close()` / context manager / `download_result_bytes`）、`streamlit` 依賴、`frontend/payload.py`（純邏輯）、`frontend/backend.py`（client 工廠）、`frontend/app.py`（Streamlit 腳本）、AppTest smoke 測試。
- **不包含**：compose / ARM64 打包（Plan 9——`ui` 服務跑 `streamlit run manim_skill/frontend/app.py` 的指令在 Plan 9 接）。前端不做 docker 端到端（Streamlit UI 自動化測試成本過高；spec §10 明定前端為薄殼、smoke test 即可，全鏈路已由 Plan 6/7 的後端 e2e 覆蓋）。

## 重要：階段與測試

- 階段機有 **5 個內部狀態**：`upload`、`analyzing`、`reviewing`、`rendering`、`done`。spec §6 列了 4 個命名階段（upload/reviewing/rendering/done）；`analyzing` 是 `rendering` 的 analyze-poll 對應狀態，補完設計、非新功能。
- 輪詢階段（`analyzing`/`rendering`）用 `st.info` + `time.sleep` + `st.rerun()` 的標準 Streamlit 輪詢模式。**AppTest 測試一律用回傳終端狀態（done/failed）的假 client**，避免踩到 `time.sleep` 迴圈。
- AppTest 測試以「直接設定 `session_state` 到某階段 → run → 斷言該階段 UI 正確 + 關鍵互動」為主，繞過難以模擬的檔案上傳。

## File Structure

```
pyproject.toml                       修改 — 加 streamlit 依賴
manim_skill/backend_client.py        修改 — 加 close() / __enter__ / __exit__ / download_result_bytes
manim_skill/frontend/__init__.py     新增（空）
manim_skill/frontend/payload.py      新增 — ConceptCard + 純邏輯（cards_from_concepts / selected_cards / build_render_payload / within_quota）
manim_skill/frontend/backend.py      新增 — build_backend_client / get_backend_client（@st.cache_resource）
manim_skill/frontend/app.py          新增 — Streamlit 腳本（5 階段）
tests/frontend/__init__.py           新增（空）
tests/frontend/test_payload.py       新增
tests/frontend/test_backend.py       新增
tests/frontend/test_app.py           新增 — AppTest smoke
tests/test_backend_client.py         修改 — 加 close / download_result_bytes 測試
```

---

## Task 1: 擴充 BackendClient + 加 streamlit 依賴

**Files:**
- Modify: `pyproject.toml`
- Modify: `manim_skill/backend_client.py`
- Modify: `tests/test_backend_client.py`

- [ ] **Step 1: 加 `streamlit` 依賴** — `pyproject.toml`：在 `dependencies` 的 `"httpx>=0.27",` 之後加一行 `"streamlit>=1.30",`。其餘不變。

- [ ] **Step 2: 重新安裝** — Run: `pip install -e ".[dev]"` → expect 成功。

- [ ] **Step 3: 在 `tests/test_backend_client.py` 末尾追加新方法的測試**

```python
def test_download_result_bytes(tmp_path, monkeypatch):
    import io

    client, store = _backend(tmp_path, monkeypatch)
    src_zip = tmp_path / "src.zip"
    with zipfile.ZipFile(src_zip, "w") as zf:
        zf.writestr("manifest.json", "{}")
    store.save(
        ServiceJob(
            job_id="j1",
            type="render",
            status=JobStatus.DONE,
            result={"zip_path": str(src_zip)},
        )
    )
    data = client.download_result_bytes("j1")
    assert isinstance(data, bytes)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert "manifest.json" in zf.namelist()


def test_close_closes_the_http_client(tmp_path, monkeypatch):
    client, _store = _backend(tmp_path, monkeypatch)
    client.close()
    assert client._client.is_closed


def test_context_manager_closes(tmp_path, monkeypatch):
    client, _store = _backend(tmp_path, monkeypatch)
    with client as entered:
        assert entered is client
    assert client._client.is_closed
```

- [ ] **Step 4: 執行測試確認失敗** — `pytest tests/test_backend_client.py -v` → expect 3 個新測試 FAIL（`download_result_bytes` / `close` 不存在）。

- [ ] **Step 5: 修改 `manim_skill/backend_client.py`** — 把現有的 `download_result` 方法取代為以下三個方法（`download_result_bytes` 新增、`download_result` 改為呼叫它、再加 `close` + context manager）：

```python
    def download_result_bytes(self, job_id: str) -> bytes:
        """The result zip's raw bytes — for in-memory use (e.g. a
        Streamlit download button)."""
        return self._request("GET", f"/jobs/{job_id}/result").content

    def download_result(self, job_id: str, dest_path) -> Path:
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(self.download_result_bytes(job_id))
        return dest_path

    def close(self) -> None:
        """Close the underlying httpx client. Safe to call once at the
        end of a process; a long-lived shared client (the Streamlit
        frontend's @st.cache_resource one) need not be closed."""
        self._client.close()

    def __enter__(self) -> "BackendClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
```

（`delete_job` / `get_catalog` 等其餘方法保持不變。）

- [ ] **Step 6: 執行測試確認通過** — `pytest tests/test_backend_client.py -v` → expect 全部 PASS（既有 10 個 + 3 個新測試 = 13）。

- [ ] **Step 7: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml manim_skill/backend_client.py tests/test_backend_client.py
git commit -m "feat: BackendClient close/context-manager + download_result_bytes; add streamlit dep"
```

---

## Task 2: frontend/payload.py — 純邏輯

**Files:**
- Create: `manim_skill/frontend/__init__.py`（空）
- Create: `tests/frontend/__init__.py`（空）
- Create: `manim_skill/frontend/payload.py`
- Create: `tests/frontend/test_payload.py`

- [ ] **Step 1: 建立空套件檔** — 空檔 `manim_skill/frontend/__init__.py` 與 `tests/frontend/__init__.py`。

- [ ] **Step 2: 寫失敗測試** — `tests/frontend/test_payload.py`:

```python
from manim_skill.frontend.payload import (
    ConceptCard,
    build_render_payload,
    cards_from_concepts,
    selected_cards,
    within_quota,
)

_CONCEPTS = [
    {"concept": "A", "why_suitable": "wa", "storyboard": "sa"},
    {"concept": "B", "why_suitable": "wb", "storyboard": "sb"},
]


def test_cards_from_concepts():
    cards = cards_from_concepts(_CONCEPTS)
    assert len(cards) == 2
    assert all(isinstance(c, ConceptCard) for c in cards)
    assert cards[0].concept == "A"
    assert cards[0].selected is True  # selected by default


def test_selected_cards_filters():
    cards = cards_from_concepts(_CONCEPTS)
    cards[1].selected = False
    result = selected_cards(cards)
    assert [c.concept for c in result] == ["A"]


def test_build_render_payload_only_selected_with_edits():
    cards = cards_from_concepts(_CONCEPTS)
    cards[0].storyboard = "edited storyboard"
    cards[1].selected = False
    payload = build_render_payload(cards)
    assert payload == [
        {
            "concept": "A",
            "why_suitable": "wa",
            "storyboard": "edited storyboard",
        }
    ]


def test_within_quota():
    cards = cards_from_concepts(_CONCEPTS)
    assert within_quota(cards, quota=5) is True
    assert within_quota(cards, quota=1) is False


def test_within_quota_counts_only_selected():
    cards = cards_from_concepts(_CONCEPTS)
    cards[0].selected = False
    assert within_quota(cards, quota=1) is True
```

- [ ] **Step 3: 執行測試確認失敗** — `pytest tests/frontend/test_payload.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: 實作** — `manim_skill/frontend/payload.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConceptCard:
    """A concept in the review stage: the analyze stage's suggestion
    plus the user's edits — the storyboard text and whether to keep it."""

    concept: str
    why_suitable: str
    storyboard: str
    selected: bool = True


def cards_from_concepts(concepts: list[dict]) -> list[ConceptCard]:
    """Turn the analyze stage's concept dicts into editable cards (all
    selected by default)."""
    return [
        ConceptCard(
            concept=c["concept"],
            why_suitable=c["why_suitable"],
            storyboard=c["storyboard"],
        )
        for c in concepts
    ]


def selected_cards(cards: list[ConceptCard]) -> list[ConceptCard]:
    return [card for card in cards if card.selected]


def build_render_payload(cards: list[ConceptCard]) -> list[dict]:
    """The concept dicts to submit as a codegen render job — only the
    selected cards, each carrying the user's (possibly edited)
    storyboard."""
    return [
        {
            "concept": card.concept,
            "why_suitable": card.why_suitable,
            "storyboard": card.storyboard,
        }
        for card in selected_cards(cards)
    ]


def within_quota(cards: list[ConceptCard], quota: int) -> bool:
    """True if the number of selected cards is within the web quota."""
    return len(selected_cards(cards)) <= quota
```

- [ ] **Step 5: 執行測試確認通過** — `pytest tests/frontend/test_payload.py -v` → expect PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add manim_skill/frontend/__init__.py manim_skill/frontend/payload.py tests/frontend/__init__.py tests/frontend/test_payload.py
git commit -m "feat: frontend payload logic (ConceptCard, render payload, quota)"
```

---

## Task 3: frontend/backend.py — Client 工廠

**Files:**
- Create: `manim_skill/frontend/backend.py`
- Create: `tests/frontend/test_backend.py`

- [ ] **Step 1: 寫失敗測試** — `tests/frontend/test_backend.py`:

```python
from manim_skill.backend_client import BackendClient
from manim_skill.frontend.backend import DEFAULT_BACKEND_URL, build_backend_client


def test_build_backend_client_uses_env(monkeypatch):
    monkeypatch.setenv("MANIM_SKILL_BACKEND", "http://spark:9000")
    client = build_backend_client()
    assert isinstance(client, BackendClient)
    assert client._base_url == "http://spark:9000"


def test_build_backend_client_explicit_url_wins(monkeypatch):
    monkeypatch.setenv("MANIM_SKILL_BACKEND", "http://spark:9000")
    client = build_backend_client("http://other:1234")
    assert client._base_url == "http://other:1234"


def test_build_backend_client_default(monkeypatch):
    monkeypatch.delenv("MANIM_SKILL_BACKEND", raising=False)
    client = build_backend_client()
    assert client._base_url == DEFAULT_BACKEND_URL.rstrip("/")
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/frontend/test_backend.py -v` → expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: 實作** — `manim_skill/frontend/backend.py`:

```python
from __future__ import annotations

import os

import streamlit as st

from manim_skill.backend_client import BackendClient

DEFAULT_BACKEND_URL = "http://localhost:8000"


def build_backend_client(url: str | None = None) -> BackendClient:
    """Build a BackendClient. The URL is the explicit `url` arg, else
    the MANIM_SKILL_BACKEND env var, else the local default."""
    resolved = url or os.environ.get(
        "MANIM_SKILL_BACKEND", DEFAULT_BACKEND_URL
    )
    return BackendClient(resolved)


@st.cache_resource
def get_backend_client() -> BackendClient:
    """One long-lived BackendClient shared across all Streamlit
    sessions and reruns — httpx clients are designed to be reused. The
    app body imports and calls this; tests monkeypatch it."""
    return build_backend_client()
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/frontend/test_backend.py -v` → expect PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/frontend/backend.py tests/frontend/test_backend.py
git commit -m "feat: frontend backend client factory"
```

---

## Task 4: frontend/app.py — Streamlit 腳本 + AppTest smoke 測試

**Files:**
- Create: `manim_skill/frontend/app.py`
- Create: `tests/frontend/test_app.py`

- [ ] **Step 1: 寫失敗測試** — `tests/frontend/test_app.py`:

```python
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
    client = FakeBackendClient()
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
    assert len(at.download_button) == 1
```

- [ ] **Step 2: 執行測試確認失敗** — `pytest tests/frontend/test_app.py -v` → expect FAIL（`manim_skill/frontend/app.py` 不存在 → AppTest 載入失敗）。

- [ ] **Step 3: 實作** — `manim_skill/frontend/app.py`:

```python
"""Streamlit frontend for manim-skill. Run with:
`streamlit run manim_skill/frontend/app.py`.

A thin shell: a 5-state stage machine over st.session_state
(upload -> analyzing -> reviewing -> rendering -> done), each stage
calling the BackendClient. All non-Streamlit logic lives in
frontend/payload.py."""

from __future__ import annotations

import time

import streamlit as st

from manim_skill.backend_client import BackendClientError
from manim_skill.frontend.backend import get_backend_client
from manim_skill.frontend.payload import (
    build_render_payload,
    cards_from_concepts,
    selected_cards,
    within_quota,
)

WEB_QUOTA = 5  # mirrors the backend's MANIM_SKILL_WEB_QUOTA default

st.set_page_config(page_title="manim-skill", layout="centered")
st.title("manim-skill")

if "stage" not in st.session_state:
    st.session_state.stage = "upload"
    st.session_state.analyze_job_id = None
    st.session_state.cards = []
    st.session_state.render_job_id = None

client = get_backend_client()


def _reset() -> None:
    st.session_state.stage = "upload"
    st.session_state.analyze_job_id = None
    st.session_state.cards = []
    st.session_state.render_job_id = None


stage = st.session_state.stage

if stage == "upload":
    st.subheader("1. 上傳素材")
    kind = st.selectbox("輸入類型", ["text", "code", "pdf"])
    guide = st.text_area("引導 prompt（選填）", value="")
    uploaded = st.file_uploader("選擇檔案")
    if st.button("分析", disabled=uploaded is None):
        try:
            job_id = client.submit_analyze(
                uploaded.getvalue(), kind, guide or None
            )
            st.session_state.analyze_job_id = job_id
            st.session_state.stage = "analyzing"
            st.rerun()
        except BackendClientError as exc:
            st.error(f"後端錯誤：{exc}")

elif stage == "analyzing":
    st.subheader("分析中…")
    try:
        job = client.get_job(st.session_state.analyze_job_id)
    except BackendClientError as exc:
        st.error(f"後端錯誤：{exc}")
        if st.button("重新開始"):
            _reset()
            st.rerun()
        st.stop()
    if job["status"] == "done":
        st.session_state.cards = cards_from_concepts(
            job["result"]["concepts"]
        )
        st.session_state.stage = "reviewing"
        st.rerun()
    elif job["status"] == "failed":
        st.error(f"分析失敗：{job.get('error')}")
        if st.button("重新開始"):
            _reset()
            st.rerun()
    else:
        st.info("處理中，稍候…")
        time.sleep(2)
        st.rerun()

elif stage == "reviewing":
    st.subheader("2. 審核概念")
    cards = st.session_state.cards
    for index, card in enumerate(cards):
        with st.container(border=True):
            card.selected = st.checkbox(
                card.concept, value=card.selected, key=f"sel_{index}"
            )
            st.caption(f"為何適合：{card.why_suitable}")
            card.storyboard = st.text_area(
                "分鏡（可編輯）",
                value=card.storyboard,
                key=f"sb_{index}",
            )
    n_selected = len(selected_cards(cards))
    st.write(f"已選 {n_selected} / {WEB_QUOTA}")
    if not within_quota(cards, WEB_QUOTA):
        st.warning(f"網頁服務每任務最多 {WEB_QUOTA} 個概念")
    can_render = within_quota(cards, WEB_QUOTA) and n_selected >= 1
    col_back, col_render = st.columns(2)
    if col_back.button("← 重新分析"):
        _reset()
        st.rerun()
    if col_render.button("開始渲染 ▶", disabled=not can_render):
        try:
            job_id = client.submit_render_concepts(
                build_render_payload(cards)
            )
            st.session_state.render_job_id = job_id
            st.session_state.stage = "rendering"
            st.rerun()
        except BackendClientError as exc:
            st.error(f"後端錯誤：{exc}")

elif stage == "rendering":
    st.subheader("3. 渲染中…")
    try:
        job = client.get_job(st.session_state.render_job_id)
    except BackendClientError as exc:
        st.error(f"後端錯誤：{exc}")
        if st.button("重新開始"):
            _reset()
            st.rerun()
        st.stop()
    if job["status"] == "done":
        st.session_state.stage = "done"
        st.rerun()
    elif job["status"] == "failed":
        st.error(f"渲染失敗：{job.get('error')}")
        if st.button("重新開始"):
            _reset()
            st.rerun()
    else:
        st.info("渲染中，稍候…")
        time.sleep(3)
        st.rerun()

elif stage == "done":
    st.subheader("4. 完成")
    job_id = st.session_state.render_job_id
    try:
        zip_bytes = client.download_result_bytes(job_id)
    except BackendClientError as exc:
        st.error(f"下載失敗：{exc}")
        st.stop()
    st.download_button(
        "下載 zip",
        data=zip_bytes,
        file_name=f"{job_id}.zip",
        mime="application/zip",
    )
    if st.button("完成並清除"):
        try:
            client.delete_job(job_id)
        except BackendClientError:
            pass
        _reset()
        st.rerun()
```

- [ ] **Step 4: 執行測試確認通過** — `pytest tests/frontend/test_app.py -v` → expect PASS (8 passed)。
  若 `AppTest` 的某個元素存取方式在安裝的 Streamlit 版本上不同（例如 `at.download_button` / `at.file_uploader` 的名稱），執行 `python -c "from streamlit.testing.v1 import AppTest; print([a for a in dir(AppTest) if not a.startswith('_')])"` 確認可用屬性並調整測試的存取方式（`app.py` 不需改）。

- [ ] **Step 5: 執行完整非 docker 套件確認無回歸** — `pytest -m "not docker" -q` → expect 全部 PASS.

- [ ] **Step 6: Commit**

```bash
git add manim_skill/frontend/app.py tests/frontend/test_app.py
git commit -m "feat: Streamlit frontend app (5-stage upload/analyze/review/render/done)"
```

---

## Self-Review

**1. Spec coverage（對照 Phase 2 設計文件 §6 Streamlit 前端）**

- 4 個命名階段 upload/reviewing/rendering/done（+ `analyzing` 為 analyze-poll 對應狀態）→ Task 4 `app.py` 的階段機 ✓
- `session_state` 持有 `stage` / `analyze_job_id` / 概念清單（含編輯）/ `render_job_id` → Task 4 ✓
- upload 階段：檔案上傳 + kind 選擇 + 選填 guide prompt + 「分析」按鈕 → Task 4 `upload` 分支 ✓
- 概念審核：全部就地可編輯（分鏡 textarea + checkbox）、沒有獨立編輯模式 → Task 4 `reviewing` 分支（每張卡片一個 checkbox + 一個 text_area）✓
- 「開始渲染」是唯一 commit 點、之前的編輯只改 session_state → Task 4：編輯直接寫回 `card.selected`/`card.storyboard`（session_state 內），只有按「開始渲染」才呼叫 `submit_render_concepts` ✓
- 配額即時反映：「已選 N / 5」、超過 5 → 按鈕 disabled + 提示 → Task 4 `reviewing` 分支 + Task 2 `within_quota` ✓
- 「重新分析」連結回 upload → Task 4 `reviewing` 的「← 重新分析」按鈕 + `_reset()` ✓
- rendering 階段輪詢 RenderJob → Task 4 `rendering` 分支 ✓
- done 階段：下載 zip → 確認收到 → `DELETE` → 回 upload → Task 4 `done` 分支（`st.download_button` + 「完成並清除」按鈕呼叫 `delete_job` + `_reset()`）✓
- Streamlit 邏輯薄、純邏輯抽出獨立可測 → Task 2 `payload.py`（`build_render_payload`/`within_quota` 等）✓
- 用 `streamlit.testing.AppTest` 做輕量 smoke test → Task 4 的 8 個 AppTest 測試 ✓
- 共用 `backend_client`（Plan 7）→ Task 3 `build_backend_client` 包 `BackendClient`；Task 1 補上前端需要的 `download_result_bytes` 與 `close()`（回應 Plan 7 review 的前瞻提醒）✓

**不在本計畫範圍（Plan 9）：** docker-compose 的 `ui` 服務指令（`streamlit run manim_skill/frontend/app.py`）、ARM64 打包。已在範圍界定說明。

**2. Placeholder scan：** 無 TBD/TODO。每個 step 有完整程式碼或精確指令。Task 1 / Task 4 對既有檔案的修改以「把 X 取代為 Y」「在末尾追加」的精確內容呈現。Task 4 Step 4 對 AppTest 元素存取的版本差異給了具體查證方向。輪詢階段的 `time.sleep` 已在「重要：階段與測試」說明，且測試策略明確避開（假 client 回終端狀態）。

**3. Type consistency：**
- `ConceptCard(concept, why_suitable, storyboard, selected=True)`、`cards_from_concepts(list[dict]) -> list[ConceptCard]`、`selected_cards`、`build_render_payload(cards) -> list[dict]`、`within_quota(cards, quota) -> bool`（Task 2）→ Task 4 `app.py` 一致 import 與使用、Task 4 測試建構 `ConceptCard("Attention", "w", "s1")` 與簽名一致。
- `build_backend_client(url=None) -> BackendClient`、`get_backend_client()`、`DEFAULT_BACKEND_URL`（Task 3）→ Task 4 `app.py` `from manim_skill.frontend.backend import get_backend_client`、Task 4 測試 monkeypatch `backend_mod.get_backend_client`、Task 3 測試使用 `build_backend_client` 與 `DEFAULT_BACKEND_URL`，一致。
- `BackendClient` 擴充方法 `download_result_bytes(job_id) -> bytes`、`close()`、`__enter__`/`__exit__`（Task 1）→ Task 4 `app.py` `done` 分支用 `download_result_bytes`；Task 1 測試一致。
- `app.py` 用到的 client 方法 `submit_analyze(content, kind, guide_prompt)`、`get_job(job_id)`、`submit_render_concepts(concepts)`、`download_result_bytes(job_id)`、`delete_job(job_id)` — 與 Plan 7 的 `BackendClient` 簽名一致；Task 4 測試的 `FakeBackendClient` 鏡像同樣的方法簽名。
- 後端 job 狀態 doc 欄位（`status`/`result`/`error`、analyze 的 `result.concepts`）— 與 Plan 6 的 `ServiceJob.to_dict()` 一致。

無不一致。

---

## Execution Handoff

Plan 完成並存於 `docs/superpowers/plans/2026-05-14-plan-8-streamlit-frontend.md`。將以 subagent-driven-development 執行（依使用者既定偏好，不再詢問）。波次：Task 1 與 Task 2 互相獨立可平行；Task 3 依賴 Task 1（streamlit 安裝）；Task 4 依賴 Task 1–3。

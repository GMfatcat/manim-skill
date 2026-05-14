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
    st.session_state.zip_bytes = None

client = get_backend_client()


def _reset() -> None:
    st.session_state.stage = "upload"
    st.session_state.analyze_job_id = None
    st.session_state.cards = []
    st.session_state.render_job_id = None
    st.session_state.zip_bytes = None


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
    if st.session_state.analyze_job_id is None:
        _reset()
        st.rerun()
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
    if st.session_state.get("zip_bytes") is None:
        try:
            st.session_state.zip_bytes = client.download_result_bytes(job_id)
        except BackendClientError as exc:
            st.error(f"下載失敗：{exc}")
            st.stop()
    zip_bytes = st.session_state.zip_bytes
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

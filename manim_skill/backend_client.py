from __future__ import annotations

import time
from pathlib import Path

import httpx


class BackendClientError(RuntimeError):
    """Raised when a call to the manim-skill backend fails (transport
    error, non-2xx status, or a poll timeout)."""


class BackendClient:
    """HTTP client for the manim-skill backend job API. Shared by the
    CLI's remote render mode and the Streamlit frontend. Pass a custom
    `http_client` (e.g. an httpx.Client over an ASGITransport) for
    in-process testing."""

    def __init__(
        self,
        base_url: str,
        *,
        http_client: httpx.Client | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client or httpx.Client(
            base_url=self._base_url, timeout=timeout
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendClientError(
                f"{method} {path} failed: {exc}"
            ) from exc
        if resp.status_code >= 400:
            raise BackendClientError(
                f"{method} {path} -> HTTP {resp.status_code}: {resp.text}"
            )
        return resp

    def submit_render_spec(self, spec: dict) -> str:
        resp = self._request(
            "POST", "/render", json={"mode": "spec", "payload": spec}
        )
        return resp.json()["job_id"]

    def submit_render_concepts(self, concepts: list) -> str:
        resp = self._request(
            "POST",
            "/render",
            json={"mode": "codegen", "payload": concepts},
        )
        return resp.json()["job_id"]

    def submit_analyze(
        self, content: bytes, kind: str, guide_prompt: str | None = None
    ) -> str:
        data = {"kind": kind}
        if guide_prompt:
            data["guide_prompt"] = guide_prompt
        resp = self._request(
            "POST",
            "/analyze",
            files={"file": ("input", content)},
            data=data,
        )
        return resp.json()["job_id"]

    def get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/jobs/{job_id}").json()

    def wait_for_job(
        self,
        job_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: float = 1800.0,
    ) -> dict:
        """Poll until the job is done or failed; return its status doc.
        Raises BackendClientError on timeout."""
        deadline = time.monotonic() + timeout
        while True:
            job = self.get_job(job_id)
            if job["status"] in ("done", "failed"):
                return job
            if time.monotonic() > deadline:
                raise BackendClientError(
                    f"timed out waiting for job {job_id}"
                )
            time.sleep(poll_interval)

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

    def delete_job(self, job_id: str) -> None:
        self._request("DELETE", f"/jobs/{job_id}")

    def get_catalog(self) -> str:
        return self._request("GET", "/catalog").json()["catalog"]

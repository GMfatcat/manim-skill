from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from manim_skill.backend_client import BackendClient, BackendClientError

from manim_skill.llm.catalog import build_component_catalog
from manim_skill.render.backend import render_batch
from manim_skill.render.jobs import JobStatus
from manim_skill.skill_docs import generate_skill_docs
from manim_skill.spec.parse import SpecParseError, parse_spec_text
from manim_skill.spec.validate import SpecValidationError, validate_spec


def _load_spec(spec_path: str):
    text = Path(spec_path).read_text(encoding="utf-8")
    return validate_spec(parse_spec_text(text))


def _cmd_validate(args) -> int:
    try:
        spec = _load_spec(args.spec)
    except (SpecParseError, SpecValidationError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(spec.beats)} beat(s), title={spec.title!r}")
    return 0


def _cmd_catalog(args) -> int:
    print(build_component_catalog())
    return 0


def _cmd_render(args) -> int:
    try:
        text = Path(args.spec).read_text(encoding="utf-8")
        raw = parse_spec_text(text)
    except (SpecParseError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    backend_url = args.remote or os.environ.get("MANIM_SKILL_BACKEND")
    if backend_url:
        return _render_remote(raw, backend_url, args.workdir)

    try:
        spec = validate_spec(raw)
    except SpecValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    batch = render_batch([spec], Path(args.workdir))
    clip = batch.clip_jobs[0]
    if clip.status == JobStatus.DONE:
        print(f"mp4: {clip.mp4_path}")
        print(f"gif: {clip.gif_path}")
        print(f"zip: {batch.zip_path}")
        return 0
    print(f"RENDER FAILED: {clip.error}", file=sys.stderr)
    return 1


def _render_remote(raw_spec: dict, backend_url: str, workdir: str) -> int:
    """Submit a spec to a deployed backend, poll, download the result.
    The backend validates the spec — the agent path's 'repair loop' is
    the agent rewriting the spec and re-running render."""
    client = BackendClient(backend_url)
    try:
        job_id = client.submit_render_spec(raw_spec)
        print(f"submitted: {job_id} (backend: {backend_url})")
        job = client.wait_for_job(job_id)
        if job["status"] != "done":
            print(
                f"RENDER FAILED: {job.get('error')}", file=sys.stderr
            )
            return 1
        zip_path = client.download_result(
            job_id, Path(workdir) / f"{job_id}.zip"
        )
        client.delete_job(job_id)
        print(f"zip: {zip_path}")
        return 0
    except BackendClientError as exc:
        print(f"BACKEND ERROR: {exc}", file=sys.stderr)
        return 1


def _cmd_gen_skill_docs(args) -> int:
    written = generate_skill_docs(args.skill_dir)
    for path in written:
        print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manim-skill",
        description="Turn manim scene specs into rendered animations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a scene spec")
    p_validate.add_argument("spec", help="path to a scene spec JSON file")
    p_validate.set_defaults(func=_cmd_validate)

    p_catalog = sub.add_parser(
        "catalog", help="print the component catalog"
    )
    p_catalog.set_defaults(func=_cmd_catalog)

    p_render = sub.add_parser("render", help="render a scene spec")
    p_render.add_argument("spec", help="path to a scene spec JSON file")
    p_render.add_argument(
        "--workdir",
        default="manim_skill_out",
        help="working/output directory (default: manim_skill_out)",
    )
    p_render.add_argument(
        "--remote",
        default=None,
        help=(
            "backend URL for remote rendering (or set "
            "MANIM_SKILL_BACKEND); if unset, renders locally in-process"
        ),
    )
    p_render.set_defaults(func=_cmd_render)

    p_gen = sub.add_parser(
        "gen-skill-docs",
        help="regenerate the agent skill reference docs",
    )
    p_gen.add_argument(
        "--skill-dir",
        default="skill",
        help="the skill directory (default: skill)",
    )
    p_gen.set_defaults(func=_cmd_gen_skill_docs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

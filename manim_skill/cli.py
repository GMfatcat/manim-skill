from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from manim_skill.backend_client import BackendClient, BackendClientError

from manim_skill.llm.analyze import ConceptCandidate, analyze
from manim_skill.llm.catalog import build_component_catalog
from manim_skill.llm.client import OpenAIClient
from manim_skill.llm.codegen import CodegenError, generate_spec
from manim_skill.llm.input_prep import prepare_input
from manim_skill.render.backend import render_batch
from manim_skill.render.jobs import JobStatus
from manim_skill.skill_docs import generate_skill_docs
from manim_skill.spec.parse import SpecParseError, parse_spec_text
from manim_skill.spec.validate import SpecValidationError, validate_spec


def _load_spec(spec_path: str):
    text = Path(spec_path).read_text(encoding="utf-8")
    return validate_spec(parse_spec_text(text))


def _build_llm_client_from_env() -> OpenAIClient:
    """Build an OpenAIClient from MANIM_SKILL_LLM_* env vars.

    Defaults match service/config.py so a local Ollama or vLLM works
    out of the box. The api_key field is optional — local servers
    typically don't require one, OpenRouter / OpenAI do.
    """
    base_url = os.environ.get(
        "MANIM_SKILL_LLM_BASE_URL", "http://localhost:11434/v1"
    )
    model = os.environ.get("MANIM_SKILL_LLM_MODEL", "qwen3.5-35b")
    api_key = os.environ.get("MANIM_SKILL_LLM_API_KEY", "not-needed")
    return OpenAIClient(base_url=base_url, model=model, api_key=api_key)


def _read_input_for_kind(path: Path, kind: str):
    if kind == "pdf":
        return path.read_bytes()
    return path.read_text(encoding="utf-8")


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
    batch = render_batch([spec], Path(args.workdir), quality=args.quality)
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


def _cmd_analyze(args) -> int:
    """Run the LLM analyze stage and dump concepts.json into workdir."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"INVALID: {input_path} not found", file=sys.stderr)
        return 1
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    content = _read_input_for_kind(input_path, args.kind)
    prepared = prepare_input(content, args.kind)
    client = _build_llm_client_from_env()
    concepts = analyze(client, prepared, guide_prompt=args.guide)

    out = workdir / "concepts.json"
    out.write_text(
        json.dumps(
            [c.model_dump() for c in concepts], indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )
    print(f"analyze: {len(concepts)} concept(s) saved to {out}")
    for i, c in enumerate(concepts):
        print(f"  [{i}] {c.concept}")
    return 0


def _cmd_codegen_concepts(args) -> int:
    """Read workdir/concepts.json and codegen a spec_NN.json per concept."""
    workdir = Path(args.workdir)
    concepts_path = workdir / "concepts.json"
    if not concepts_path.exists():
        print(
            f"INVALID: {concepts_path} not found (run `analyze` first)",
            file=sys.stderr,
        )
        return 1

    raw = json.loads(concepts_path.read_text(encoding="utf-8"))
    concepts = [ConceptCandidate.model_validate(c) for c in raw]

    if args.indices:
        try:
            picked = [int(x) for x in args.indices.split(",") if x.strip()]
        except ValueError:
            print(f"INVALID: bad --indices {args.indices!r}", file=sys.stderr)
            return 1
    else:
        picked = list(range(len(concepts)))

    catalog = build_component_catalog()
    client = _build_llm_client_from_env()

    ok = 0
    failed = 0
    for i in picked:
        if i < 0 or i >= len(concepts):
            print(f"  [{i}] SKIP (out of range)", file=sys.stderr)
            continue
        concept = concepts[i]
        try:
            spec = generate_spec(client, concept, catalog)
            (workdir / f"spec_{i:02d}.json").write_text(
                spec.model_dump_json(indent=2), encoding="utf-8"
            )
            print(f"  [{i}] OK  {concept.concept} — {len(spec.beats)} beats")
            ok += 1
        except CodegenError as exc:
            print(f"  [{i}] FAIL {concept.concept} — {exc}")
            failed += 1
    print(f"codegen-concepts: {ok} spec(s) saved, {failed} failed")
    return 0


def _cmd_bundle(args) -> int:
    """Load every spec_*.json under workdir, render as one batch, write zip."""
    workdir = Path(args.workdir)
    spec_paths = sorted(workdir.glob("spec_*.json"))
    if not spec_paths:
        print(
            f"INVALID: no spec_*.json files under {workdir}", file=sys.stderr
        )
        return 1

    specs = []
    for p in spec_paths:
        try:
            text = p.read_text(encoding="utf-8")
            specs.append(validate_spec(parse_spec_text(text)))
        except (SpecParseError, SpecValidationError) as exc:
            print(f"INVALID: {p.name}: {exc}", file=sys.stderr)
            return 1

    batch = render_batch(specs, workdir, quality=args.quality)
    print(f"bundle: {len(specs)} clip(s), status={batch.status.value}")
    for i, clip in enumerate(batch.clip_jobs):
        ok_beats = sum(1 for bj in clip.beat_jobs if bj.mp4_path)
        total = len(clip.beat_jobs)
        print(
            f"  [{i}] {clip.spec.title}: {ok_beats}/{total} beats, "
            f"status={clip.status.value}"
        )
    if batch.zip_path:
        print(f"zip: {batch.zip_path}")
    return 0


def _cmd_demo(args) -> int:
    """End-to-end: analyze -> (pause for review) -> codegen -> bundle.

    The pause between analyze and codegen lets a human edit
    workdir/concepts.json (drop / reorder / rewrite concepts) before
    paying for codegen. Skip the pause with --yes (or when an agent is
    driving and confirming via its own UI).
    """
    rc = _cmd_analyze(args)
    if rc != 0:
        return rc

    if not args.yes:
        concepts_path = Path(args.workdir) / "concepts.json"
        print(
            f"\nEdit {concepts_path} now to drop / reorder / rewrite "
            f"concepts.\nPress ENTER to continue with codegen + bundle, "
            f"or Ctrl-C to abort."
        )
        try:
            input("")
        except (KeyboardInterrupt, EOFError):
            print("\naborted by user", file=sys.stderr)
            return 1

    args.indices = None
    rc = _cmd_codegen_concepts(args)
    if rc != 0:
        return rc
    return _cmd_bundle(args)


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
    p_render.add_argument(
        "--quality",
        choices=["low", "medium", "high", "production", "fourk"],
        default="medium",
        help=(
            "render quality (default: medium = 720p30). "
            "low=480p15, medium=720p30, high=1080p60, "
            "production=1440p60, fourk=2160p60. "
            "Ignored when using --remote (the backend picks)."
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

    p_analyze = sub.add_parser(
        "analyze",
        help="LLM stage 1: extract concept candidates from an input file",
    )
    p_analyze.add_argument("input", help="path to text / code / PDF input")
    p_analyze.add_argument(
        "--kind", choices=["text", "code", "pdf"], required=True
    )
    p_analyze.add_argument(
        "-o", "--workdir", default="manim_skill_out",
        help="output directory (default: manim_skill_out)",
    )
    p_analyze.add_argument(
        "--guide", default=None,
        help="optional one-line guide prompt added to the LLM input",
    )
    p_analyze.set_defaults(func=_cmd_analyze)

    p_codegen = sub.add_parser(
        "codegen-concepts",
        help="LLM stage 2: turn workdir/concepts.json into spec_NN.json files",
    )
    p_codegen.add_argument(
        "workdir", help="directory holding concepts.json (from `analyze`)"
    )
    p_codegen.add_argument(
        "--indices", default=None,
        help="comma-separated subset of concept indices to codegen "
             "(default: all)",
    )
    p_codegen.set_defaults(func=_cmd_codegen_concepts)

    p_bundle = sub.add_parser(
        "bundle",
        help="render every spec_*.json under workdir as one batch + zip",
    )
    p_bundle.add_argument("workdir", help="directory holding spec_*.json")
    p_bundle.add_argument(
        "--quality",
        choices=["low", "medium", "high", "production", "fourk"],
        default="medium",
    )
    p_bundle.set_defaults(func=_cmd_bundle)

    p_demo = sub.add_parser(
        "demo",
        help="end-to-end: analyze -> pause for review -> codegen -> bundle",
    )
    p_demo.add_argument("input", help="path to text / code / PDF input")
    p_demo.add_argument(
        "--kind", choices=["text", "code", "pdf"], required=True
    )
    p_demo.add_argument(
        "-o", "--workdir", default="manim_skill_out",
        help="output directory (default: manim_skill_out)",
    )
    p_demo.add_argument("--guide", default=None)
    p_demo.add_argument(
        "--yes", action="store_true",
        help="skip the review pause between analyze and codegen",
    )
    p_demo.add_argument(
        "--quality",
        choices=["low", "medium", "high", "production", "fourk"],
        default="medium",
    )
    p_demo.set_defaults(func=_cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

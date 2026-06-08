# LaTeX Bidirectional Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect suspicious LaTeX in formula params deterministically (feeding the existing codegen re-ask) and conservatively repair the zero-risk subset at render time, so an open-source model's both-directions LaTeX escaping mistakes stop producing broken formulas.

**Architecture:** A new `manim_skill/spec/latex.py` owns all LaTeX escaping heuristics behind two pure functions sharing one command whitelist: `latex_warnings(s)` (non-destructive detection, consumed by lint → re-ask) and `repair_latex(s)` (conservative render-time rewrite). `lint_spec` calls the former on formula params; the two formula components call the latter in `build`. No spec-schema change, no codegen code change (the phase-2 lint→re-ask loop already re-asks on any warning).

**Tech Stack:** Python 3.13, manim 0.20.1, Pydantic, pytest. Spec: `docs/superpowers/specs/2026-06-08-latex-bidirectional-guard-design.md`.

---

## File Structure

- **Create** `manim_skill/spec/latex.py` — `_COMMANDS` whitelist, `repair_latex`, `latex_warnings`. One responsibility: LaTeX escaping heuristics.
- **Create** `tests/spec/test_latex.py`.
- **Modify** `manim_skill/spec/lint.py` — emit `latex_suspicious` warnings from formula params.
- **Modify** `manim_skill/components/formula_breakdown.py`, `formula_walkthrough.py` — repair formulas in `build`.
- **Modify** `tests/spec/test_lint.py`, `tests/llm/test_codegen.py`, `tests/components/test_formula_breakdown.py`, `tests/components/test_formula_walkthrough.py`.

---

## Task 1: `spec/latex.py` — heuristics module

**Files:**
- Create: `manim_skill/spec/latex.py`
- Test: `tests/spec/test_latex.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/spec/test_latex.py
from manim_skill.spec.latex import latex_warnings, repair_latex


def test_repair_glued_over_escape():
    assert repair_latex(r"\\mathbf{x} = \\mathbf{W}") == r"\mathbf{x} = \mathbf{W}"


def test_repair_formfeed_and_backspace_control_chars():
    # \f -> formfeed (\x0c) + "rac"; \b -> backspace (\x08) + "eta"
    assert repair_latex("\x0crac{a}{b}") == r"\frac{a}{b}"
    assert repair_latex("\x08eta") == r"\beta"


def test_repair_leaves_matrix_row_separators():
    src = r"\begin{matrix} a \\ b \end{matrix}"
    assert repair_latex(src) == src


def test_repair_leaves_spaced_double_backslash():
    # a spaced "\\ x" is an intended line break, not glued to a command
    assert repair_latex(r"a \\ x") == r"a \\ x"


def test_repair_leaves_correct_latex_unchanged():
    assert repair_latex(r"\frac{Q K^T}{\sqrt{d_k}}") == r"\frac{Q K^T}{\sqrt{d_k}}"


def test_repair_leaves_unknown_control_char():
    # a stray control char not forming a known command is left as-is
    assert repair_latex("\x0czz") == "\x0czz"


def test_warnings_flag_control_char():
    assert latex_warnings("\x0crac{a}{b}")  # non-empty


def test_warnings_flag_glued_over_escape():
    msgs = latex_warnings(r"\\mathbf{x}")
    assert any("mathbf" in m for m in msgs)


def test_warnings_flag_bare_command_before_brace():
    assert latex_warnings(r"frac{a}{b}")  # missing backslash before frac{


def test_warnings_clean_formula_silent():
    assert latex_warnings(r"\frac{a}{b}") == []


def test_warnings_allow_matrix_row_separator():
    assert latex_warnings(r"\begin{matrix} a \\ b \end{matrix}") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/spec/test_latex.py -q`
Expected: FAIL — `ModuleNotFoundError: manim_skill.spec.latex`.

- [ ] **Step 3: Write minimal implementation**

```python
# manim_skill/spec/latex.py
"""Deterministic LaTeX escaping heuristics for formula params.

`latex_warnings` flags suspicious LaTeX (non-destructive) for the codegen
re-ask; `repair_latex` conservatively rewrites only the zero-risk subset at
render time. Both share one command whitelist. See
docs/superpowers/specs/2026-06-08-latex-bidirectional-guard-design.md.
"""
from __future__ import annotations

import re

_COMMANDS = frozenset({
    "mathbf", "mathrm", "mathit", "mathcal", "mathbb", "mathsf", "text",
    "frac", "sqrt", "sum", "prod", "int", "lim", "cdot", "times", "div",
    "quad", "qquad", "partial", "nabla", "infty",
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta",
    "eta", "theta", "iota", "kappa", "lambda", "mu", "nu", "xi", "pi",
    "rho", "sigma", "tau", "phi", "chi", "psi", "omega",
    "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Phi",
    "Psi", "Omega",
})

# Longest-first so e.g. "qquad" is tried before "quad", "varepsilon" before
# "eta", "epsilon".
_CMD_ALT = "|".join(sorted(_COMMANDS, key=len, reverse=True))

# Two backslashes glued to a command name at a command boundary.
_GLUED = re.compile(r"\\\\(" + _CMD_ALT + r")(?![A-Za-z])")
# A control char (form-feed = decoded \f, backspace = decoded \b) followed by
# letters — an under-escaped command whose first letter is a valid JSON escape.
_CTRL_CMD = re.compile(r"([\x0c\x08])([A-Za-z]+)")
_CTRL_TO_LETTER = {"\x0c": "f", "\x08": "b"}
# Any control char except tab (\x09) and newline (\x0a) — the broad signal that
# a backslash was dropped (used by warnings only).
_CTRL_ANY = re.compile(r"[\x00-\x08\x0b\x0c\x0d\x0e-\x1f]")
# A bare command name immediately before a command-argument opener.
_BARE_CMD = re.compile(r"(?<![\\A-Za-z])(" + _CMD_ALT + r")(?=[{_^])")


def repair_latex(s: str) -> str:
    """Conservatively undo the two zero-risk escaping mistakes."""
    def _ctrl(m: re.Match) -> str:
        word = _CTRL_TO_LETTER[m.group(1)] + m.group(2)
        if any(word.startswith(cmd) for cmd in _COMMANDS):
            return "\\" + word
        return m.group(0)

    s = _CTRL_CMD.sub(_ctrl, s)
    if "\\begin{" not in s:
        s = _GLUED.sub(r"\\\1", s)
    return s


def latex_warnings(s: str) -> list[str]:
    """Non-destructive detection of suspicious LaTeX, for the re-ask hint."""
    out: list[str] = []
    if _CTRL_ANY.search(s):
        out.append(
            "a LaTeX command lost its backslash (control char in the formula); "
            "write commands like \\frac with one backslash, encoded as \\\\ in JSON"
        )
    if "\\begin{" not in s:
        for m in _GLUED.finditer(s):
            cmd = m.group(1)
            out.append(
                f"\\\\{cmd} is double-escaped; a LaTeX command needs one "
                f"backslash (\\{cmd}), not two"
            )
    for m in _BARE_CMD.finditer(s):
        out.append(f'"{m.group(1)}" looks like a LaTeX command missing its backslash')
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/spec/test_latex.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/spec/latex.py tests/spec/test_latex.py
git commit -m "feat(latex): repair_latex + latex_warnings escaping heuristics"
```

---

## Task 2: Lint integration

**Files:**
- Modify: `manim_skill/spec/lint.py`
- Test: `tests/spec/test_lint.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/spec/test_lint.py`:

```python
def test_glued_overescape_formula_warns():
    spec = _spec(
        [Beat(component="FormulaBreakdown", params={"formula": "\\\\mathbf{x}"})]
    )
    codes = [w.code for w in lint_spec(spec)]
    assert "latex_suspicious" in codes


def test_clean_formula_no_latex_warning():
    spec = _spec(
        [Beat(component="FormulaBreakdown", params={"formula": "\\frac{a}{b}"})]
    )
    assert "latex_suspicious" not in [w.code for w in lint_spec(spec)]


def test_walkthrough_segment_overescape_warns():
    spec = _spec(
        [
            Beat(
                component="FormulaWalkthrough",
                params={"segments": ["\\frac{a}{b}", "\\\\mathbf{x}"]},
            )
        ]
    )
    assert "latex_suspicious" in [w.code for w in lint_spec(spec)]
```

Note: the Python literal `"\\\\mathbf{x}"` is the string `\\mathbf{x}` (two
backslashes) — the over-escaped form `lint` must catch. `"\\frac{a}{b}"` is
`\frac{a}{b}` (one backslash) — correct.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/spec/test_lint.py -q -k "latex or formula"`
Expected: FAIL — no `latex_suspicious` code emitted yet.

- [ ] **Step 3: Write minimal implementation**

In `manim_skill/spec/lint.py`, add the import and a per-beat block that runs
`latex_warnings` on the LaTeX-bearing params. Add at the top:

```python
from manim_skill.spec.latex import latex_warnings
```

Inside `lint_spec`'s beat loop, after the existing `raw` block, add:

```python
        if beat.component == "FormulaBreakdown":
            for msg in latex_warnings((beat.params or {}).get("formula") or ""):
                warnings.append(LintWarning(i, "latex_suspicious", msg))
        if beat.component == "FormulaWalkthrough":
            for seg in (beat.params or {}).get("segments") or []:
                for msg in latex_warnings(seg):
                    warnings.append(LintWarning(i, "latex_suspicious", msg))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/spec/test_lint.py -q`
Expected: PASS (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/spec/lint.py tests/spec/test_lint.py
git commit -m "feat(lint): flag suspicious LaTeX in formula params"
```

---

## Task 3: Component repair integration

**Files:**
- Modify: `manim_skill/components/formula_breakdown.py`, `formula_walkthrough.py`
- Test: `tests/components/test_formula_breakdown.py`, `tests/components/test_formula_walkthrough.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/components/test_formula_breakdown.py`:

```python
def test_build_repairs_over_escaped_formula():
    from unittest.mock import patch

    from manim import Dot

    from manim_skill.components.formula_breakdown import (
        FormulaBreakdown,
        FormulaBreakdownParams,
    )

    with patch(
        "manim_skill.components.formula_breakdown.MathTex", return_value=Dot()
    ) as mock_mathtex:
        FormulaBreakdown().build(FormulaBreakdownParams(formula="\\\\mathbf{x}"))

    passed = mock_mathtex.call_args.args[0]
    assert passed == "\\mathbf{x}"  # repaired to a single backslash
```

Append to `tests/components/test_formula_walkthrough.py` (match its existing
MathTex-patch import style — it patches
`manim_skill.components.formula_walkthrough.MathTex`):

```python
def test_build_repairs_over_escaped_segments():
    from unittest.mock import patch

    from manim import Dot

    from manim_skill.components.formula_walkthrough import (
        FormulaWalkthrough,
        FormulaWalkthroughParams,
    )

    with patch(
        "manim_skill.components.formula_walkthrough.MathTex", return_value=Dot()
    ) as mock_mathtex:
        FormulaWalkthrough().build(
            FormulaWalkthroughParams(segments=["\\frac{a}{b}", "\\\\mathbf{x}"])
        )

    passed = list(mock_mathtex.call_args.args)
    assert passed == ["\\frac{a}{b}", "\\mathbf{x}"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/components/test_formula_breakdown.py tests/components/test_formula_walkthrough.py -q -k repairs`
Expected: FAIL — the raw `\\mathbf{x}` reaches MathTex unrepaired.

- [ ] **Step 3: Write minimal implementation**

In `manim_skill/components/formula_breakdown.py`, import `repair_latex` and wrap
the formula:

```python
from manim_skill.spec.latex import repair_latex
```
```python
        formula = MathTex(repair_latex(params.formula), color=THEME.INK)
```

In `manim_skill/components/formula_walkthrough.py`, import and wrap each segment:

```python
from manim_skill.spec.latex import repair_latex
```
```python
        formula = MathTex(
            *[repair_latex(s) for s in params.segments], color=THEME.INK
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/components/test_formula_breakdown.py tests/components/test_formula_walkthrough.py -q -k "not docker"`
Expected: PASS (existing non-docker + 2 new).

- [ ] **Step 5: Commit**

```bash
git add manim_skill/components/formula_breakdown.py manim_skill/components/formula_walkthrough.py tests/components/test_formula_breakdown.py tests/components/test_formula_walkthrough.py
git commit -m "feat(formula): repair LaTeX escaping in build before MathTex"
```

---

## Task 4: Codegen re-ask integration (test-only)

No codegen code change — `generate_spec` already re-asks on any lint warning
(phase 2). This task locks in that a LaTeX-suspicious spec drives exactly one
re-ask.

**Files:**
- Test: `tests/llm/test_codegen.py`

- [ ] **Step 1: Write the failing-then-passing test**

Append to `tests/llm/test_codegen.py` (reuse `FakeLLMClient`, `_CONCEPT`,
`generate_spec`):

```python
def test_latex_suspicious_formula_triggers_one_reask():
    import json

    bad = json.dumps({
        "title": "D", "aspect_ratio": "16:9",
        "beats": [{"component": "FormulaBreakdown", "params": {"formula": "\\\\mathbf{x}"}}],
    })
    clean = json.dumps({
        "title": "D", "aspect_ratio": "16:9",
        "beats": [{"component": "FormulaBreakdown", "params": {"formula": "\\mathbf{x}"}}],
    })
    client = FakeLLMClient(responses=[bad, clean])
    spec = generate_spec(client, _CONCEPT, catalog="(catalog)")
    assert len(client.calls) == 2  # valid-but-suspicious, then the lint re-ask
    assert spec.beats[0].params["formula"] == "\\mathbf{x}"
```

Note: `json.dumps` of the Python string `"\\\\mathbf{x}"` (two backslashes)
produces JSON with four backslashes; `generate_spec` parses it back to two
backslashes — the over-escaped form lint catches. The clean spec's
`"\\mathbf{x}"` is one backslash (correct) and is lint-silent.

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/llm/test_codegen.py -q -k latex_suspicious`
Expected: PASS already (Tasks 1–2 wired lint; the phase-2 loop re-asks). If it
FAILS with `len(client.calls) == 1`, lint isn't emitting `latex_suspicious` for
this formula — revisit Task 2.

- [ ] **Step 3: Run the full codegen suite**

Run: `python -m pytest tests/llm/test_codegen.py -q`
Expected: PASS (all existing guard/reask tests + the new one).

- [ ] **Step 4: Commit**

```bash
git add tests/llm/test_codegen.py
git commit -m "test(codegen): LaTeX-suspicious formula drives one lint re-ask"
```

---

## Task 5: Full-suite verification

- [ ] **Step 1: Fast suite**

Run: `python -m pytest -m "not docker" -q`
Expected: PASS — all prior tests plus the new latex/lint/codegen/component
tests.

- [ ] **Step 2: Rebuild image + docker formula render path**

`repair_latex` now sits in the formula components' `build`, so re-verify the
real LaTeX render in the container.

```bash
docker build -t manim-skill:latest -f docker/Dockerfile .
python -m pytest -m docker -q -k "formula or end_to_end or backend_e2e"
```
Expected: PASS — the formula components still render (repair is a no-op on
already-correct LaTeX, and corrects over-escaped input).

- [ ] **Step 3: Optional sanity — repair on the eval's broken formula**

Confirm the exact eval failure is now fixed end to end:

```bash
python -c "from manim_skill.spec.latex import repair_latex; print(repair_latex('\\\\mathbf{y} = \\\\mathbf{W}_{out} \\\\mathbf{x} + \\\\mathbf{b}'))"
```
Expected output: `\mathbf{y} = \mathbf{W}_{out} \mathbf{x} + \mathbf{b}`
(single backslashes — renders correctly).

- [ ] **Step 4: Commit (only if anything drifted)**

```bash
python -m pytest tests/test_skill_reference_current.py -q
git add -A
git commit -m "test: verify LaTeX bidirectional guard across suites" || echo "nothing to commit"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** `latex.py` (repair_latex + latex_warnings + whitelist)=Task 1;
  lint integration=Task 2; component repair integration=Task 3; codegen re-ask
  (no code change, verified)=Task 4; verification incl. docker formula path=Task 5.
  All spec sections mapped.
- **Placeholders:** none — every code step shows complete code and exact
  commands; the one conditional (Task 4 call-count) names the exact thing to
  recheck.
- **Type consistency:** `repair_latex`, `latex_warnings`, `_COMMANDS` (Task 1)
  are referenced verbatim in Tasks 2/3; `LintWarning(..., "latex_suspicious", ...)`
  matches the existing `LintWarning` dataclass; the `MathTex` patch targets match
  each component module's import path.

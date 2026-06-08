# LaTeX bidirectional guard: suspicion lint + conservative repair

**Date:** 2026-06-08
**Status:** approved design, pending implementation plan
**Builds on:** `2026-06-08-latex-backslash-detox-design.md` (parse de-tox, merged)
and the phase-2 codegen lint→re-ask loop.

## Problem

An open-source LLM emits free-form LaTeX strings for `FormulaBreakdown.formula`
and `FormulaWalkthrough.segments`. JSON escaping of LaTeX backslashes fails in
**both directions**, and the eval surfaced one of each:

- **Under-escape** — `\quad` (one backslash) is an invalid JSON escape; json5
  drops it → literal `quad`. The parse de-tox now fixes the *invalid-escape*
  subclass (`\q`, `\s`, `\a`, …). It cannot fix the subclass whose first
  letter is a *valid* escape: `\f`rac → form-feed + `rac`, `\b`eta →
  backspace + `eta` (the backslash+letter became a control character).
- **Over-escape** — `\\\\mathbf` (four backslashes) decodes to `\\mathbf`
  (two). LaTeX reads `\\` as a line break, so the `\mathbf` command is lost
  and the literal word `mathbf` leaks. The parse de-tox only *adds*
  backslashes, never removes, so it can't touch this — and reducing `\\`
  blindly is unsafe (`\\` is a legitimate row separator in matrix/align).

The deeper issue: there is no ground-truth check on a LaTeX string before it
renders. The strongest check (actually compiling) is render-time and heavy,
and "compiles" ≠ "correct" (the `\\mathbf` case rendered without error but was
visually broken). So this design takes the pragmatic middle: **detect
suspicious LaTeX deterministically, let the model self-correct via the existing
re-ask loop, and keep a conservative deterministic repair as a render-time net
for the zero-risk subset.** A render-compile repair loop (option B) is
explicitly deferred.

## Design

### Layering (upstream → render)

```
parse de-tox (exists)            fixes the invalid-escape under-escape subset
  → lint suspicion (NEW, F)      flags remaining suspicious LaTeX
    → codegen re-ask (exists)    model self-corrects, once, non-destructively
      → repair_latex (NEW, C)    render-time net for the zero-risk subset
        → render
```

Each layer has a distinct job: **F** gets the model to produce correct LaTeX
(cleanest, non-destructive); **C** catches what F missed or didn't re-ask, but
only the subset that can be rewritten with no risk. The web/LLM path benefits
from both; the agent path (no codegen) benefits from **C** at render.

### New module `manim_skill/spec/latex.py`

The single home for LaTeX escaping heuristics, sharing one command whitelist.

**Command whitelist** (`_COMMANDS`, a frozenset, extensible): commonly-seen
LaTeX commands whose bare/glued appearance signals an escaping error —
`mathbf, mathrm, mathit, mathcal, mathbb, text, frac, sqrt, sum, prod, int,
lim, cdot, times, div, quad, qquad, partial, nabla, infty` and the Greek
letters (`alpha, beta, gamma, delta, epsilon, varepsilon, zeta, eta, theta,
iota, kappa, lambda, mu, nu, xi, pi, rho, sigma, tau, phi, chi, psi, omega`
and their capitalized forms where applicable).

**`repair_latex(s: str) -> str`** — conservative, zero-risk rewrites only:

1. **Control-char restore (under-escape, valid-escape subclass).** Replace a
   form-feed `\x0c` with `\f` and a backspace `\x08` with `\b`, but ONLY when
   the following letter run forms a whitelisted command (e.g. `\x0c` + `rac` →
   `\frac`; `\x08` + `eta` → `\beta`). Form-feed and backspace are never
   legitimate in a math formula, so this is unambiguous. **Tab `\x09`, newline
   `\x0a`, CR `\x0d` are NOT touched** — they may be intended whitespace; those
   stay for F to re-ask.
2. **Glued over-escape.** If the string contains NO `\begin{` (no matrix/align
   environment where `\\` is a real row separator), replace `\\<cmd>` — two
   backslashes immediately followed by a whitelisted command name at a command
   boundary (`(?![a-zA-Z])`) — with `\<cmd>`. A spaced `\\ x` (intended line
   break) is left untouched because it is not glued to a command.

`repair_latex` returns the string unchanged when nothing matches.

**`latex_warnings(s: str) -> list[str]`** — non-destructive detection, returns
human-readable messages for the re-ask. Flags:

- **control characters** — any byte `< 0x20` except `\t`/`\n` present (the
  dropped-backslash control-char subclass): `"a LaTeX command lost its
  backslash (control char in formula); write e.g. \\frac with two backslashes"`.
- **glued over-escape** — a `\\<cmd>` (whitelisted, boundary) outside a
  `\begin{` environment: `"\\<cmd> is double-escaped; a single LaTeX command
  needs one backslash (\<cmd>), not two"`.
- **bare command word** — a whitelisted command name appearing with NO
  preceding backslash in a command-like position (followed by `{`, `_`, `^`,
  or standalone): `"\"<cmd>\" looks like a LaTeX command missing its
  backslash"`.

Both functions share `_COMMANDS`. Detection (`latex_warnings`) is broader than
repair (`repair_latex`): it flags ambiguous cases (tab/newline whitespace,
bare words) that repair deliberately does not rewrite, so the model gets the
chance to fix them cleanly.

### Integration points (all small)

- **`manim_skill/spec/lint.py`** — `lint_spec` collects the LaTeX-bearing
  params of `FormulaBreakdown` (`formula`) and `FormulaWalkthrough`
  (`segments`, each element), runs `latex_warnings` on each, and emits a
  `latex_suspicious` `LintWarning` per message. Advisory, like the existing
  rules; it flows into the phase-2 codegen re-ask automatically.
- **`manim_skill/components/formula_breakdown.py`** and
  **`formula_walkthrough.py`** — `build` passes each formula/segment through
  `repair_latex` before constructing `MathTex`. (LaTeX colour/theme handling
  from phase 1 is unchanged.)
- **prompt** — unchanged; the phase-1/de-tox/over-escape rules already cover
  both directions, and the lint re-ask carries the concrete per-formula hint.

### Testing (TDD)

- `tests/spec/test_latex.py`:
  - `repair_latex`: `\\mathbf{x}` → `\mathbf{x}`; form-feed+`rac` → `\frac`;
    backspace+`eta` → `\beta`; a string containing `\begin{matrix}` with `\\`
    rows is left **unchanged**; a spaced `\\ x` is left unchanged; a clean
    `\frac{a}{b}` is unchanged; a non-command stray control char is left as-is.
  - `latex_warnings`: fires once each for a control char, a glued `\\mathbf`,
    and a bare `frac{...}`; returns `[]` for a clean formula and for a correct
    `\begin{matrix}...\\...` line break.
- `tests/spec/test_lint.py`: a spec whose FormulaBreakdown formula is
  `\\mathbf{x}` yields a `latex_suspicious` warning; a clean formula yields
  none.
- `tests/llm/test_codegen.py`: a FakeLLMClient returning a valid spec with a
  glued-over-escape formula first and a clean one second causes exactly one
  re-ask and returns the clean spec (reuses the phase-2 lint-reask path).
- `tests/components/test_formula_breakdown.py` /
  `test_formula_walkthrough.py`: after `build`, the formula no longer contains
  the glued `\\mathbf` (assert via the MathTex mock the existing tests use —
  the patched `MathTex` receives the repaired string).
- existing docker formula-render tests stay green.

## Non-goals / risks

- **No render-compile repair loop (option B)** and **no structured-params
  rewrite (option A).** If F+C proves insufficient, B is a separate project.
- `repair_latex` is bounded by the `\begin{` guard, the glued-command
  constraint, and the form-feed/backspace-only control-char rule, keeping
  false-positive rewrites very unlikely. Genuinely ambiguous cases
  (tab/newline whitespace, intended line breaks, bare English words) are left
  for `latex_warnings` + re-ask, never rewritten.
- The whitelist is necessarily incomplete; an unlisted command that is
  mis-escaped is simply not caught (no false positive, just a miss) — the
  whitelist is one edit to extend.

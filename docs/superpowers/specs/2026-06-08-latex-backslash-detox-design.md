# LaTeX backslash de-tox at parse + prompt reinforcement

**Date:** 2026-06-08
**Status:** approved design, implement inline (small)
**Motivated by:** the phase-2 OpenRouter eval — `nvidia/nemotron-3-super-120b-a12b:free`
produced a FormulaBreakdown whose `\quad K = XW_K` rendered as literal
`quadK = XW_K`.

## Root cause

`parse_spec_text` tries strict `json.loads`, then falls back to `json5`.
A single-backslash LaTeX command in the model's JSON is an **invalid JSON
escape** (`\q`, `\s`, `\a`, …); strict parse fails, and json5's lenient
string handling **drops the backslash** (`\quad` → `quad`, `\sqrt` → `sqrt`).
Worse, a single backslash before a *valid* escape char becomes a control
character (`\frac` → form-feed + `rac`, since `\f` = U+000C). The codegen
prompt already tells the model to double-escape (`\\frac`); the model mostly
complies but slipped on the spacing command `\quad`.

## Design

Two layers — deterministic recovery for the recoverable subclass, prompt for
the rest.

### 1. Parse-time de-tox (`manim_skill/spec/parse.py`)

Between the strict `json.loads` attempt and the `json5` fallback, repair the
candidate by **doubling invalid JSON escape sequences**, then retry strict
`json.loads` (and pass the repaired text to json5 too):

- Valid JSON escape chars after `\`: `" \ / b f n r t u`.
- Replace any `\` NOT followed by one of those with `\\` (regex
  `\\(?![\"\\/bfnrtu])` → `\\\\`).
- Effect: lone `\quad` → `\\quad` → decodes to `\quad` (preserved as proper
  LaTeX). Already-doubled `\\frac` is untouched (its first `\` is followed by
  `\`, a valid escape char). Legitimate `\n`/`\t` inside strings (e.g. a
  caption newline, a raw-beat `\n`) are valid escapes → untouched.

Order in `parse_spec_text`:
1. `json.loads(candidate)` (strict, unchanged).
2. on failure: `candidate = double_invalid_escapes(candidate)`, retry
   `json.loads`.
3. on failure: `json5.loads(candidate)` (now on the repaired text).
4. on failure: `SpecParseError` (unchanged message path).

**Known limitation (documented, not fixed here):** commands whose first
letter forms a *valid* escape — `\f`rac, `\t`imes, `\b`eta, `\n`abla,
`\r`ho — become control chars under a single backslash and are NOT
recoverable by this rule. Those rely on the prompt rule below. This mirrors
the existing `exec_raw` `\\n` recovery philosophy (recover the common,
unambiguous case; don't over-reach).

### 2. Prompt reinforcement (`manim_skill/llm/codegen.py`)

In `_CODEGEN_SYSTEM`'s LaTeX rules, state explicitly that **every** LaTeX
command — including spacing commands like `\quad`, `\,`, `\;` — must be
written with a doubled backslash in JSON, and extend the worked example to
include `\\quad`.

## Testing (TDD)

- `tests/spec/test_parse.py`:
  - a spec JSON with single-backslash `\quad`, `\sqrt`, `\alpha` parses with
    the backslashes preserved (`\quad` etc. in the decoded `formula`).
  - already-doubled `\\frac` decodes to `\frac` (unchanged behavior).
  - a legitimate `\n` inside a string stays a real newline (not doubled).
  - a clean, valid JSON object is unaffected (strict path still wins).
- `tests/llm/test_codegen.py`: the LaTeX guard test (or a new assertion)
  confirms the prompt mentions `\quad` / spacing commands. The existing
  `test_codegen_system_prompt_includes_latex_backslash_guard` must still pass.

## Non-goals

- No change to the spec schema or FormulaBreakdown rendering.
- No attempt to recover `\f\t\b\n\r`-prefixed commands at parse time.
- No new dependency.

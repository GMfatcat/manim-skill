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
    # arrows / relations
    "rightarrow", "leftarrow", "Rightarrow", "Leftarrow", "leftrightarrow",
    "to", "mapsto", "implies", "leq", "geq", "neq", "approx", "equiv",
    "propto", "sim", "cong",
    # dots
    "cdots", "ldots", "dots", "vdots", "ddots",
    # delimiters
    "left", "right", "langle", "rangle", "lfloor", "rfloor", "lceil", "rceil",
    # accents / styling
    "hat", "bar", "vec", "tilde", "overline", "boldsymbol",
    # operators
    "log", "exp", "sin", "cos", "tan", "max", "min", "arg", "det", "dim",
})

# Longest-first so e.g. "qquad" is tried before "quad", "varepsilon" before
# "eta"/"epsilon".
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

# Static Harness: a framework-level theme layer

**Date:** 2026-06-07
**Status:** approved design, pending implementation plan

## Problem

The `manim-skill` framework turns a concept into a manim animation. In the
production (web) path an **open-source LLM** writes the scene spec; on the
agent path an external agent does. Either way, the quality ceiling of the
*deterministic* parts of the system is what a weak model can lean on.

The `dlm-polish/` exercise (a hand-crafted slide deck, now retired as a
one-off demo) showed that **even a strong model needed many revision rounds**
to reach a polished result. The recurring fixes clustered tightly:

- **Layout / overlap** — arrows occluding labels, banners over charts, boxes
  overlapping.
- **Typography** — italics look bad; uneven Latin kerning (`parallel`
  rendered as `para llel` from Pango per-glyph fallback); too-small sizes.
- **Narration discipline** — the more text packed on screen, the more layout
  and kerning trouble; trimming narration helped.
- **Composition** — `camera` reuse fails in manim 0.20.x.

The factory deploys mainly open-source models, which are unlikely to clear
that bar by generation alone. So the leverage is to **move quality from
"the model gets it right" into "the deterministic layer makes it right by
default."**

### Key finding from the current codebase

The framework has **no theme layer today.** Each of the 14 component modules
hardcodes its own colors, fonts, and sizes inline (61 such occurrences;
e.g. `text_beat.py` hardcodes `font_size` 56/36 and imports nothing about
style). Consequences:

- No consistent palette across a multi-clip deliverable.
- No font configuration → no IBM Plex / kerning workaround → the `para llel`
  defect can recur in **any** component that uses `Text`.
- No safe-default text factories → font sizes are ad hoc per component.

`dlm-polish/shared.py` already crystallized the missing layer (semantic
palette, font config with the kerning workaround, text factories with safe
defaults, reusable primitives). This design lifts that knowledge into the
framework as a **static, deterministic harness** — no extra model calls.

## Scope (phase 1 — "foundation layer")

In scope:

1. A framework-level **theme module**.
2. **Refactoring the 14 components** to draw color/font/size from the theme.
3. **Builder** sets the scene background from the theme.
4. **Raw-beat** namespace exposes theme tokens + text factories.
5. A few **codegen prompt** visual rules (DO/DO NOT, same style as the
   existing raw-beat guards).

Explicitly **out of scope** (deferred to later phases):

- Layout-safety helpers (safe-area margins, fit-text-to-width, safe vstack).
- New higher-level components (token-box, section-divider, two-column slide).
- Spec-level lint warnings.
- A spec-schema `theme` field. Theme selection is via env var, not the spec.
- Any dynamic render→critique→fix loop (a different, opt-out-of design).

## Design

### A. `manim_skill/components/theme.py`

A semantic, swappable theme. The default is a **neutral light** palette —
deliberately neither the dlm-polish cream nor manim's black — so arbitrary
concepts get a consistent, calm look without imposing a "research report"
aesthetic. The dlm warm palette ships as a named preset.

**`Theme` dataclass** (frozen) with semantic color tokens:

```
BG  BG_CARD  BG_CODE  INK  INK_SOFT  INK_FAINT
PRIMARY  PRIMARY_SOFT  WARN  HIGHLIGHT  RULE
```

**Presets** (same token set, different hex):

| token | `NEUTRAL` (default) | `DLM_WARM` |
|-------|--------------------|------------|
| BG | `#F7F6F3` | `#FBF8F1` |
| BG_CARD | `#EEEDE8` | `#F4F0E6` |
| BG_CODE | `#E8E7E1` | `#ECE7D9` |
| INK | `#1A1A1A` | `#1A1A1A` |
| INK_SOFT | `#44443F` | `#4A4A48` |
| INK_FAINT | `#76746C` | `#7A7872` |
| PRIMARY | `#34597A` | `#1E4F5C` |
| PRIMARY_SOFT | `#5E7D94` | `#3D7480` |
| WARN | `#9A3B2E` | `#8B3A2E` |
| HIGHLIGHT | `#E8DCA8` | `#F4E9C9` |
| RULE | `#C9C5B8` | `#C8C2B0` |

(The exact `NEUTRAL` hex values are a starting point and are trivially
tunable — they live in one place.)

**Active theme.** A module-level `THEME` (a `Theme` instance), default
`NEUTRAL`, selected at import time from env var `MANIM_SKILL_THEME`
(`neutral` | `dlm_warm`; unknown → `neutral`). This mirrors the existing
`MANIM_SKILL_RENDER_QUALITY` env-config pattern and keeps the spec schema
untouched. A `get_theme(name)` helper resolves a name to a preset.

**Fonts** (module constants, carrying the kerning-workaround rationale as a
comment lifted from `shared.py`):

```
FONT_DISPLAY = "IBM Plex Sans"     # NOT "...Sans TC" — that font isn't in
FONT_BODY    = "IBM Plex Serif"    # the IBM/plex repo, so Pango would fall
FONT_MONO    = "IBM Plex Mono"     # back per-glyph and break Latin kerning.
```
CJK characters fall through to the bundled Noto CJK automatically.

**Text factories** (safe defaults; read the active `THEME`):

- `title_text(text, *, size=48, color=None)` — display font, bold.
- `body_text(text, *, size=28, color=None)` — body font, **not italic** (no
  `italic` param at all in phase 1 — italics are banned).
- `caption_text(text, *, size=22, color=None)` — body font.
- `label_text(text, *, size=18, color=None)` — mono font.

`color=None` resolves to the appropriate theme token **inside** the function
(title/body/caption → `INK`/`INK_SOFT`; label → `INK_FAINT`), not as a
default-argument expression — so switching `THEME` (or a future per-call
theme) is honored at call time rather than frozen at def time. Each returns a
manim `Text` with font + size + color preset. Sizes are the "don't go too
small" floor learned from dlm-polish.

**Spacing constants:** `GAP = 0.35`, `MARGIN = 0.6` (scene-unit defaults for
component authors; richer layout helpers are phase 2).

### B. Component refactor

Each of the 14 components replaces inline colors/fonts/sizes with theme
tokens and text factories. Mapping rule: a component's existing color
*role* maps to the nearest semantic token (a primary/emphasis color →
`PRIMARY`, an error/highlight-red → `WARN`, body text → `INK`/`INK_SOFT`,
faint labels → `INK_FAINT`, default manim `BLUE`/`WHITE` on the old black
bg → the corresponding ink/primary token on the new light bg). Visual
*intent* is preserved; the values are now centralized, consistent, and
kerning-safe.

Components must not set their own scene background (see C).

### C. Builder

`builder/spec_scene.py` (`SpecScene`) sets `self.camera.background_color =
THEME.BG` once during setup, so every clip shares the themed background and
no component needs to. (This replaces the per-component / manim-default
background.)

### D. Raw beat integration

`builder/raw.py` injects the theme names into the raw-beat exec namespace,
alongside the manim names it already pre-imports: the active `THEME` object,
the individual color tokens, the font constants, and the four text
factories. This makes the codegen prompt rule "use theme colors / factories"
actionable — the names exist when the raw code runs.

### E. Codegen prompt

`llm/codegen.py` `_CODEGEN_SYSTEM` gains a **VISUAL RULES** block, same
DO/DO NOT shape as the existing raw-beat and LaTeX guards:

- DO NOT use italics.
- Keep `caption` short (a few words, not a sentence).
- DO NOT pack many lines of text into one beat — fewer elements, more space.
- In raw beats, use the theme colors (`PRIMARY`, `INK`, `WARN`, …) and the
  text factories (`title_text(...)`, `body_text(...)`, …) instead of
  hardcoded colors/fonts; do NOT set a background.

`llm/catalog.py` appends the available theme token / factory names to the
raw-beat guidance section so the model knows what it may call.

## Testing (TDD — tests first)

- **theme unit** (`tests/components/test_theme.py`): both presets expose the
  same token set; `get_theme` resolves names and falls back to `NEUTRAL`;
  env var selects the active theme; each text factory returns a `Text` with
  the expected font and size and **non-italic** slant.
- **component tests**: the existing 14 component tests stay green. Add a
  representative assertion that a component pulls from the theme rather than a
  hardcoded literal (assert on font/token usage, **not** exact hex, to keep
  the palette tunable).
- **builder** (`tests/builder/test_spec_scene.py`): `SpecScene` sets the
  camera background to `THEME.BG`.
- **raw beat** (`tests/builder/test_raw.py`): theme tokens and factories are
  present in the exec namespace; a raw beat referencing `PRIMARY` /
  `title_text(...)` runs without `NameError`.
- **codegen prompt guard** (`tests/llm/test_codegen.py`): a new test asserts
  the VISUAL RULES (no-italics, short-caption, use-theme) persist in
  `_CODEGEN_SYSTEM`, matching the existing guard-test pattern.
- **skill-reference drift** (`tests/test_skill_reference_current.py`): if the
  catalog output changes, regenerate `skill/reference/*.md` so the drift test
  stays green.

## Non-goals / risks

- The neutral palette is a taste call; it is isolated to one module and
  tunable. Existing components' bright defaults (`BLUE`/`WHITE`) will look
  wrong on a light bg until refactored — so the refactor (B) and the theme
  (A) must land together, not piecemeal, to avoid a half-themed look.
- No behavioral guarantee against overlap — overlap isn't statically
  decidable and layout-safety helpers are phase 2. This phase fixes
  palette + typography + kerning consistency, which is the bulk of what
  dlm-polish fought, not geometric layout.
```

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

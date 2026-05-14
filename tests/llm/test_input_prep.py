from manim_skill.llm.input_prep import prepare_input


def test_text_passthrough():
    assert prepare_input("hello world", "text") == "hello world"


def test_code_passthrough():
    code = "def f():\n    return 1"
    assert prepare_input(code, "code") == code


def test_bytes_text_decoded():
    assert prepare_input(b"hi there", "text") == "hi there"


def test_pdf_extraction(monkeypatch):
    import pypdf

    class _FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class _FakeReader:
        def __init__(self, _src):
            self.pages = [_FakePage("page one"), _FakePage("page two")]

    monkeypatch.setattr(pypdf, "PdfReader", _FakeReader)
    result = prepare_input(b"%PDF-fake-bytes", "pdf")
    assert "page one" in result
    assert "page two" in result

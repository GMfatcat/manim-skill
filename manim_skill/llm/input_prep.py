from __future__ import annotations

import io
from typing import Literal

InputKind = Literal["text", "code", "pdf"]


def prepare_input(content, kind: InputKind) -> str:
    """Normalize raw input into plain text for the analyze stage.

    - "text" / "code": returned as-is (decoded from bytes if needed).
    - "pdf": text extracted from every page via pypdf; `content` may be
      raw PDF bytes or a path.
    """
    if kind == "pdf":
        import pypdf

        if isinstance(content, (bytes, bytearray)):
            reader = pypdf.PdfReader(io.BytesIO(content))
        else:
            reader = pypdf.PdfReader(content)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()

    if isinstance(content, (bytes, bytearray)):
        return content.decode("utf-8", errors="replace")
    return str(content)

import os

from ..core.config import ASK_MAX_CHARS
from ..core.utils import decode_excerpt

_BINARY = {"kind": "binary", "content": None, "truncated": False}


def _cap_text(text):
    """Shared tail handling for both byte-decoded text and extracted document
    text: trim to ASK_MAX_CHARS and add the [showing first ~N KB] marker the
    UI and prompt already understand."""
    if len(text) <= ASK_MAX_CHARS:
        return {"kind": "text", "content": text, "truncated": False}
    cut = text.rfind("\n", 0, ASK_MAX_CHARS)
    if cut > ASK_MAX_CHARS // 2:
        text = text[:cut]
    else:
        text = text[:ASK_MAX_CHARS]
    kb = max(1, len(text) // 1024)
    return {"kind": "text", "content": f"[showing first ~{kb} KB]\n{text}", "truncated": True}


def _extract_pdf(path):
    """pypdf page-text extraction. Returns extracted text, or None when the
    file is unreadable/corrupt (caller falls back to the binary path)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
    except ImportError:
        return None
    except Exception:
        return None
    parts = []
    budget = ASK_MAX_CHARS + 4096
    try:
        for page in reader.pages:
            parts.append(page.extract_text() or "")
            if sum(len(p) for p in parts) >= budget:
                break
    except Exception:
        return None
    return "\n".join(parts).strip()


def _extract_docx(path):
    """python-docx paragraph extraction (tables are skipped: paragraphs are the
    readable skeleton the model needs). Returns text, or None when unreadable."""
    try:
        from docx import Document
        document = Document(path)
    except ImportError:
        return None
    except Exception:
        return None
    parts = []
    budget = ASK_MAX_CHARS + 4096
    for paragraph in document.paragraphs:
        parts.append(paragraph.text)
        if sum(len(p) for p in parts) >= budget:
            break
    return "\n".join(parts).strip()


def read_for_ask(path):
    """Return {"kind": text|binary, "content", "truncated"} for the Ask
    endpoints. Text files are byte-decoded; PDFs and DOCX get real document
    extraction (Phase 5); anything the extractors cannot read falls back to
    the binary metadata summary."""
    ext = os.path.splitext(str(path))[1].lower()
    if ext == ".pdf":
        extracted = _extract_pdf(path)
        if extracted:
            return _cap_text(extracted)
        return dict(_BINARY)
    if ext == ".docx":
        extracted = _extract_docx(path)
        if extracted:
            return _cap_text(extracted)
        return dict(_BINARY)
    try:
        size = os.path.getsize(path)
    except OSError:
        return dict(_BINARY)
    try:
        with open(path, "rb") as fh:
            head = fh.read(ASK_MAX_CHARS + 1)
    except OSError:
        return dict(_BINARY)
    text = decode_excerpt(head)
    if text is None:
        return dict(_BINARY)
    truncated = size > len(head)
    if truncated:
        cut = text.rfind("\n", 0, ASK_MAX_CHARS)
        if cut > ASK_MAX_CHARS // 2:
            text = text[:cut]
        else:
            text = text[:ASK_MAX_CHARS]
        kb = max(1, len(text) // 1024)
        text = f"[showing first ~{kb} KB]\n{text}"
    return {"kind": "text", "content": text, "truncated": truncated}

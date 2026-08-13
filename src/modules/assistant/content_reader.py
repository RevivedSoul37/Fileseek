import os

from ..core.config import ASK_MAX_CHARS
from ..core.utils import decode_excerpt


def read_for_ask(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return {"kind": "binary", "content": None, "truncated": False}
    try:
        with open(path, "rb") as fh:
            head = fh.read(ASK_MAX_CHARS + 1)
    except OSError:
        return {"kind": "binary", "content": None, "truncated": False}
    text = decode_excerpt(head)
    if text is None:
        return {"kind": "binary", "content": None, "truncated": False}
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

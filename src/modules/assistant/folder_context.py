import os

from ..core.config import ASK_MORE_EXCERPT_CHARS, ASK_MORE_EXCERPT_FILES, ASK_MORE_MAX_SIBLINGS
from ..core.utils import decode_excerpt, get_file_category

_EXCERPT_CATEGORIES = {"document", "code", "data"}


def build_folder_context(path):
    folder = os.path.dirname(os.path.abspath(path))
    try:
        entries = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        return {"folder": folder, "siblings": [], "excerpts": {}, "hidden": 0}
    basename = os.path.basename(path).lower()
    siblings = []
    for entry in entries:
        full = os.path.join(folder, entry)
        try:
            stat = os.stat(full)
        except OSError:
            continue
        if os.path.isdir(full):
            siblings.append({"name": entry + "/", "size": 0, "category": "folder"})
            continue
        extension = os.path.splitext(entry)[1].lower()
        siblings.append({
            "name": entry,
            "size": stat.st_size,
            "category": get_file_category(extension),
        })
    siblings = [s for s in siblings if s["name"].lower() != basename and s["name"].lower() != basename + "/"]
    hidden = max(0, len(siblings) - ASK_MORE_MAX_SIBLINGS)
    shown = siblings[:ASK_MORE_MAX_SIBLINGS]
    excerpts = {}
    candidates = [
        s for s in shown
        if s["category"] in _EXCERPT_CATEGORIES and 0 < s["size"] <= ASK_MORE_EXCERPT_CHARS
    ]
    candidates.sort(key=lambda s: s["size"])
    for s in candidates[:ASK_MORE_EXCERPT_FILES]:
        full = os.path.join(folder, s["name"])
        try:
            with open(full, "rb") as fh:
                head = fh.read(ASK_MORE_EXCERPT_CHARS)
        except OSError:
            continue
        text = decode_excerpt(head)
        if text:
            excerpts[s["name"]] = text
    return {"folder": folder, "siblings": shown, "excerpts": excerpts, "hidden": hidden}

import difflib


def _classify(old_text, new_text):
    old_lines = (old_text or "").splitlines()
    new_lines = (new_text or "").splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    added = removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "insert"):
            added += j2 - j1
        if tag in ("replace", "delete"):
            removed += i2 - i1
    return added, removed


def summarize_diff(old_snapshot, new_snapshot):
    """Compare two snapshots (dicts with 'hash', 'size', 'text') and return the
    last_diff_* metadata fields. Caller must have already verified the content
    hash actually changed."""
    old_size = (old_snapshot or {}).get("size") or 0
    new_size = (new_snapshot or {}).get("size") or 0
    size_delta = new_size - old_size
    old_text = (old_snapshot or {}).get("text")
    new_text = (new_snapshot or {}).get("text")

    if old_text is None or new_text is None:
        return {
            "last_diff_summary": None,
            "last_diff_lines_added": 0,
            "last_diff_lines_removed": 0,
            "last_diff_size_delta": size_delta,
            "last_diff_kind": "binary",
        }

    added, removed = _classify(old_text, new_text)
    parts = []
    if added:
        parts.append(f"{added} line{'s' if added != 1 else ''} added")
    if removed:
        parts.append(f"{removed} line{'s' if removed != 1 else ''} removed")
    if not parts:
        if size_delta:
            parts.append(f"same lines, size {'+' if size_delta > 0 else ''}{size_delta} B")
        else:
            parts.append("identical text")
    return {
        "last_diff_summary": " \u00b7 ".join(parts),
        "last_diff_lines_added": added,
        "last_diff_lines_removed": removed,
        "last_diff_size_delta": size_delta,
        "last_diff_kind": "text",
    }


def size_only_fields(old_size, new_size):
    """Diff fields for events where no line diff is possible (binary files, or
    the first change after indexing where no 'before' excerpt existed yet)."""
    size_delta = (new_size or 0) - (old_size or 0)
    return {
        "last_diff_summary": None,
        "last_diff_lines_added": 0,
        "last_diff_lines_removed": 0,
        "last_diff_size_delta": size_delta,
        "last_diff_kind": "size-only",
    }

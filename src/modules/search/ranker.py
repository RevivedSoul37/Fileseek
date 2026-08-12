from ..core.utils import format_size, time_ago

SEMANTIC_WEIGHT = 0.60
EXACT_WEIGHT = 0.25
RECENCY_WEIGHT = 0.10
SIZE_WEIGHT = 0.05

RECENCY_HALFLIFE_DAYS = 30.0


def _stem(name):
    base = name.lower()
    if "." in base:
        return base.rsplit(".", 1)[0]
    return base


def _exact_score(query, record):
    q = query.lower().strip()
    name = record["name"].lower()
    stem = _stem(name)
    if not q:
        return 0.0
    if q == name:
        return 1.0
    if q == stem:
        return 0.95
    if stem.startswith(q):
        coverage = len(q) / max(len(stem), 1)
        return 0.75 + 0.15 * min(1.0, coverage)
    if q in name:
        coverage = len(q) / max(len(stem), 1)
        return 0.55 + 0.20 * min(1.0, coverage)
    words = q.split()
    if words:
        hit_words = sum(1 for w in words if len(w) >= 3 and (w in stem))
        if hit_words:
            return 0.25 * (hit_words / len(words))
    return 0.0


def _recency_score(modified, now):
    if not modified:
        return 0.0
    age_days = max(0.0, (now - modified) / 86400.0)
    return 0.5 ** (age_days / RECENCY_HALFLIFE_DAYS)


def _size_score(size):
    if not size or size <= 0:
        return 0.0
    if size < 100:
        return 0.4
    return 1.0


def rank(hits, query, now):
    ranked = []
    for hit in hits:
        record = hit["record"]
        semantic = max(0.0, min(1.0, hit["score"]))
        exact = _exact_score(query, record)
        recency = _recency_score(record.get("modified"), now)
        size = _size_score(record.get("size"))
        final = (
            SEMANTIC_WEIGHT * semantic
            + EXACT_WEIGHT * exact
            + RECENCY_WEIGHT * recency
            + SIZE_WEIGHT * size
        )
        ranked.append((final, semantic, hit))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked


def record_to_result(record, match_percent=None, semantic_percent=None):
    return {
        "name": record["name"],
        "path": record["path"],
        "parent_folder": record.get("parent_folder", ""),
        "extension": record.get("extension", ""),
        "size": record.get("size", 0),
        "size_display": format_size(record.get("size", 0)),
        "modified": record.get("modified"),
        "modified_display": time_ago(record.get("modified")),
        "category": record.get("category", "other"),
        "icon": record.get("icon", "\U0001F4C1"),
        "sensitive": bool(record.get("sensitive")),
        "match_percent": match_percent,
        "semantic_percent": semantic_percent,
    }


def decorate(ranked_hits):
    results = []
    for final, semantic, hit in ranked_hits:
        results.append(record_to_result(
            hit["record"],
            match_percent=int(round(final * 100)),
            semantic_percent=int(round(semantic * 100)),
        ))
    return results

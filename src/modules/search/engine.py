import time

from ..core.config import MAX_RESULTS, SEARCH_COUNT_POOL, SEARCH_MATCH_FLOOR
from . import ranker


class SearchEngine:
    def __init__(self, store, embedder):
        self.store = store
        self.embedder = embedder

    def search(self, query, max_results=None, category=None):
        query = (query or "").strip()
        if not query:
            return []
        limit = max_results or MAX_RESULTS
        fetch_k = max(limit * 3, SEARCH_COUNT_POOL)
        started = time.perf_counter()
        query_vec = self.embedder.embed_query(query)
        hits = self.store.search(query_vec, k=fetch_k)
        ranked = ranker.rank(hits, query, time.time())
        decorated = ranker.decorate(ranked)
        decorated = [r for r in decorated
                     if (r.get("match_percent") or 0) >= SEARCH_MATCH_FLOOR * 100]
        counts = {}
        for result in decorated:
            counts[result["category"]] = counts.get(result["category"], 0) + 1
        total = len(decorated) if not category or category == "all" else counts.get(category, 0)
        if category and category != "all":
            decorated = [r for r in decorated if r["category"] == category]
        decorated = decorated[:limit]
        elapsed_ms = (time.perf_counter() - started) * 1000
        for result in decorated:
            result["elapsed_ms"] = round(elapsed_ms, 1)
        return decorated, {"total": total, "categories": counts}

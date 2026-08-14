import time

from ..core.config import CONTENT_MATCH_FLOOR, MAX_RESULTS, SEARCH_COUNT_POOL, SEARCH_MATCH_FLOOR
from . import ranker


def _make_snippet(text, window=140):
    """Collapse a chunk to a one-line 140-char window for the card."""
    if not text:
        return ""
    return " ".join(text.split())[:window]


class SearchEngine:
    def __init__(self, store, embedder):
        self.store = store
        self.embedder = embedder

    def _search_names(self, query_vec, query, fetch_k):
        """Classic name/folder search: {path: result}."""
        hits = self.store.search(query_vec, k=fetch_k)
        decorated = ranker.decorate(ranker.rank(hits, query, time.time()))
        results = {}
        for result in decorated:
            if (result.get("match_percent") or 0) >= SEARCH_MATCH_FLOOR * 100:
                results[result["path"]] = result
        return results

    def _search_contents(self, query_vec, query, fetch_k, content_index):
        """Chunk hits aggregated onto their parent file card, carrying the
        best-matching chunk as a snippet. {path: result}."""
        chunk_hits = content_index.search(query_vec, k=fetch_k)
        by_file = {}
        for hit in chunk_hits:
            key = hit["file_key"]
            if key not in by_file or hit["score"] > by_file[key]["score"]:
                by_file[key] = hit
        fake_hits = []
        snippets = {}
        for key, hit in by_file.items():
            if hit["score"] < CONTENT_MATCH_FLOOR:
                continue
            record = self.store.get_record(key) if self.store.is_ready() else None
            if record is None:
                continue
            fake_hits.append({"score": hit["score"], "record": record})
            snippets[record["path"]] = _make_snippet(hit["snippet"])
        results = {}
        for result in ranker.decorate(ranker.rank(fake_hits, query, time.time())):
            result["snippet"] = snippets.get(result["path"], "")
            results[result["path"]] = result
        return results

    def search(self, query, max_results=None, category=None, scope="files", content_index=None):
        """scope = files | contents | both. `files` is the classic search;
        `contents` ranks files by their best text-chunk hit and shows a
        snippet; `both` merges them, the snippet winning on overlap."""
        query = (query or "").strip()
        if not query:
            return []
        limit = max_results or MAX_RESULTS
        fetch_k = max(limit * 3, SEARCH_COUNT_POOL)
        started = time.perf_counter()
        query_vec = self.embedder.embed_query(query)

        results = {}
        want_names = scope in ("files", "both")
        want_contents = (
            scope in ("contents", "both")
            and content_index is not None
            and content_index.ready
        )
        if want_names:
            results.update(self._search_names(query_vec, query, fetch_k))
        if want_contents:
            for path, result in self._search_contents(query_vec, query, fetch_k, content_index).items():
                if path in results:
                    results[path]["snippet"] = result["snippet"]
                else:
                    results[path] = result

        final = list(results.values())
        final.sort(key=lambda r: (r.get("match_percent") or 0), reverse=True)
        counts = {}
        for result in final:
            counts[result["category"]] = counts.get(result["category"], 0) + 1
        total = len(final) if not category or category == "all" else counts.get(category, 0)
        if category and category != "all":
            final = [r for r in final if r["category"] == category]
        final = final[:limit]
        elapsed_ms = (time.perf_counter() - started) * 1000
        for result in final:
            result["elapsed_ms"] = round(elapsed_ms, 1)
        return final, {"total": total, "categories": counts}

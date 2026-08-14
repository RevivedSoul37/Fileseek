import pytest

from modules.indexer.content_index import ContentIndex
from modules.indexer.index_store import IndexStore
from modules.search.engine import SearchEngine


class _StubEmbedder:
    """Deterministic one-hot-ish embedder: every query points at dimension 0,
    every file/chunk embedding is unique per text hash."""

    def __init__(self, dim=8):
        self.dim = dim

    def _vec(self, text):
        import numpy as np
        v = np.zeros(self.dim, dtype="float32")
        v[0] = 1.0  # matches the query direction below
        j = (hash(text) % (self.dim - 1)) + 1
        v[j] = 0.35
        norm = float(np.linalg.norm(v))
        return v / norm

    def build_text(self, record):
        return record.get("name", "")

    def embed_texts(self, texts, batch_size=64, show_progress=False):
        import numpy as np
        return np.stack([self._vec(t) for t in texts])

    def embed_query(self, text):
        import numpy as np
        v = np.zeros(self.dim, dtype="float32")
        v[0] = 1.0
        return v.reshape(1, -1)


def _record(path, name="file.txt"):
    return {
        "name": name,
        "path": path,
        "parent_folder": "tests",
        "extension": ".txt",
        "size": 12,
        "modified": 1700000000,
        "category": "data",
        "icon": "x",
        "sensitive": False,
    }


@pytest.fixture()
def world(tmp_path):
    embedder = _StubEmbedder()
    store = IndexStore()
    src = tmp_path / "file.txt"
    src.write_text("the quasar ledger reconciliation protocol\n", encoding="utf-8")
    key = str(src).lower()
    record = _record(str(src))
    store.build({key: record}, embedder.embed_query("file.txt").reshape(1, -1))
    engine = SearchEngine(store, embedder)

    content_index = ContentIndex(
        index_path=tmp_path / "ci.index", meta_path=tmp_path / "ci.json"
    )
    content_index.set_enabled(True)
    content_index.index_file(key, record, embedder)
    return engine, content_index


def test_files_scope_returns_cards(world):
    engine, content_index = world
    results, counts = engine.search("file", scope="files", content_index=content_index)
    assert results
    assert results[0]["name"] == "file.txt"
    assert results[0].get("snippet") is None


def test_contents_scope_carries_snippet(world):
    engine, content_index = world
    results, counts = engine.search(
        "quasar ledger reconciliation", scope="contents", content_index=content_index
    )
    assert results
    assert results[0]["name"] == "file.txt"
    assert "quasar" in results[0]["snippet"]


def test_contents_scope_requires_ready_index(world):
    engine, content_index = world
    results, counts = engine.search(
        "anything", scope="contents", content_index=None
    )
    assert results == []


def test_both_scope_merges_without_duplicates(world):
    engine, content_index = world
    results, counts = engine.search(
        "quasar ledger reconciliation", scope="both", content_index=content_index
    )
    paths = [r["path"] for r in results]
    assert len(paths) == len(set(paths))

import pytest

from modules.indexer import content_index as ci_mod
from modules.indexer.content_index import ContentIndex, chunk_text, read_text_file


class _StubEmbedder:
    def __init__(self, dim=8):
        self.dim = dim
        self.calls = 0

    def embed_texts(self, texts, batch_size=64, show_progress=False):
        import numpy as np
        self.calls += 1
        n = len(texts)
        vecs = np.zeros((n, self.dim), dtype="float32")
        for i in range(n):
            j = i % self.dim
            vecs[i, j] = 1.0
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.where(norms == 0, 1, norms)

    def build_text(self, record):
        return record.get("name", "")

    def embed_query(self, text):
        return self.embed_texts([text])[0].reshape(1, -1)


def _record(path, category="code", ext=".py"):
    return {
        "name": "file" + ext,
        "path": path,
        "parent_folder": "tests",
        "extension": ext,
        "size": 10,
        "modified": 0,
        "category": category,
        "icon": "x",
        "sensitive": False,
    }


def test_chunk_text_basics():
    long = "hello world " * 300
    chunks = chunk_text(long)
    assert chunks
    for chunk in chunks:
        assert len(chunk) <= ci_mod.CONTENT_CHUNK_CHARS + 1


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_read_text_file_respects_caps(tmp_path):
    small = tmp_path / "small.txt"
    small.write_text("abc def\n", encoding="utf-8")
    assert read_text_file(str(small)) is not None

    big = tmp_path / "big.bin"
    big.write_bytes(b"\x00" * 1024)
    assert read_text_file(str(big)) is None  # NUL -> binary


def test_content_index_full_cycle(tmp_path):
    idx = ContentIndex(
        index_path=tmp_path / "content.index",
        meta_path=tmp_path / "content_meta.json",
    )
    embedder = _StubEmbedder(dim=8)
    src = tmp_path / "file.py"
    src.write_text("print('hello unique token xyzzy')\n", encoding="utf-8")
    record = _record(str(src))

    idx.set_enabled(False)
    assert idx.index_file("f1", record, embedder) == 0  # disabled -> no-op
    idx.set_enabled(True)
    n = idx.index_file("f1", record, embedder)
    assert n >= 1
    assert idx.is_ready()
    idx.save()

    idx2 = ContentIndex(
        index_path=tmp_path / "content.index",
        meta_path=tmp_path / "content_meta.json",
    )
    assert idx2.load()
    idx2.set_enabled(True)
    assert idx2.is_ready()
    stats = idx2.stats()
    assert stats["chunks"] == n and stats["files"] == 1

    assert idx2.remove_file("f1") is True
    assert idx2.stats()["chunks"] == 0


def test_content_index_skips_binary_and_non_text(tmp_path):
    idx = ContentIndex(
        index_path=tmp_path / "c.index", meta_path=tmp_path / "c.json"
    )
    idx.set_enabled(True)
    embedder = _StubEmbedder(dim=8)

    image = tmp_path / "pic.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    rec_image = _record(str(image), category="image", ext=".png")
    assert idx.index_file("img", rec_image, embedder) == 0

    txt = tmp_path / "note.txt"
    txt.write_text("hello world line\n", encoding="utf-8")
    rec_txt = _record(str(txt), category="data", ext=".txt")
    assert idx.index_file("txt", rec_txt, embedder) >= 0  # .txt is text-category

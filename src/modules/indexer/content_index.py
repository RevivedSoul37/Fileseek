import json
import os
import threading
import time
from pathlib import Path

import faiss
import numpy as np

from ..core.config import (
    CONTENT_CHUNK_CHARS,
    CONTENT_CHUNK_STRIDE,
    CONTENT_INDEX_PATH,
    CONTENT_MAX_CHUNKS_PER_FILE,
    CONTENT_MAX_FILE_BYTES,
    CONTENT_META_PATH,
)

_TEXT_CATEGORIES = {"code", "data", "document"}
_TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
    ".json", ".jsonl", ".ndjson", ".xml", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".html", ".htm", ".css", ".py", ".js", ".ts", ".jsx", ".tsx", ".bat", ".ps1",
    ".sh", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".java", ".sql",
}
_CHUNK_LIMIT_BYTES = 64 * 1024


def chunk_text(text, size=None, stride=None):
    """Split into ~CHAR-sized windows with a stride overlap so phrases
    straddling a boundary still land whole in some window."""
    size = size or CONTENT_CHUNK_CHARS
    stride = stride or CONTENT_CHUNK_STRIDE
    if not text:
        return []
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks = []
    for start in range(0, len(text), stride):
        chunk = text[start:start + size]
        if chunk.strip():
            chunks.append(chunk)
        if start + size >= len(text):
            break
    return chunks[:CONTENT_MAX_CHUNKS_PER_FILE]


def read_text_file(path):
    """Read a text-category file as utf-8, capped. Returns the text or None
    when the file is binary, too big, or unreadable."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size <= 0 or size > CONTENT_MAX_FILE_BYTES:
        return None
    try:
        with open(path, "rb") as fh:
            head = fh.read(_CHUNK_LIMIT_BYTES)
    except OSError:
        return None
    if b"\x00" in head:
        return None
    try:
        return head.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        try:
            return head.decode("cp1252")
        except UnicodeDecodeError:
            return None


class ContentIndex:
    """Second IndexIDMap over ~500-char text windows. The key contract: every
    metadata entry remembers its parent file path + a snippet source, so the
    search engine can aggregate hits back onto the file card. Off by default:
    only populated when settings.json sets content_index_enabled."""

    def __init__(self, index_path=None, meta_path=None):
        self.index_path = Path(index_path or CONTENT_INDEX_PATH)
        self.meta_path = Path(meta_path or CONTENT_META_PATH)
        self.index = None
        self.metadata = {}
        self.path_to_id = {}
        self.dim = None
        self.enabled = False
        self.built_at = None
        self.lock = threading.RLock()

    @property
    def ready(self):
        """Accepting writes: the feature flag is on. Use is_ready() when you
        need actual vectors to search."""
        return self.enabled

    def is_ready(self):
        return self.ready and self.index is not None and self.index.ntotal > 0

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled = bool(enabled)

    def _fresh_index(self, dim):
        self.dim = dim
        flat = faiss.IndexFlatIP(dim)
        self.index = faiss.IndexIDMap(flat)
        self.metadata = {}
        self.path_to_id = {}
        self.built_at = time.time()

    def index_file(self, file_key, record, embedder):
        """Chunk + embed one file. Binary or oversized files return 0."""
        if not self.ready:
            return 0
        if record.get("category") not in _TEXT_CATEGORIES:
            return 0
        ext = (record.get("extension") or "").lower()
        if ext not in _TEXT_EXTENSIONS:
            return 0
        text = read_text_file(record.get("path", ""))
        if not text:
            return 0
        self.remove_file(file_key)
        chunks = chunk_text(text)
        if not chunks:
            return 0
        embeddings = embedder.embed_texts(chunks, batch_size=32, show_progress=False)
        with self.lock:
            if self.index is None or self.dim != int(embeddings.shape[1]):
                self._fresh_index(int(embeddings.shape[1]))
            ids = np.arange(self._next_id(), self._next_id() + len(chunks), dtype="int64")
            self.index.add_with_ids(embeddings, ids)
            for chunk_id, chunk in zip(ids, chunks):
                self.metadata[int(chunk_id)] = {
                    "file_key": file_key,
                    "path": record.get("path"),
                    "name": record.get("name"),
                    "snippet": chunk,
                }
                self.path_to_id.setdefault(file_key, [])
                self.path_to_id[file_key].append(int(chunk_id))
            return len(chunks)

    def build_from_store(self, store, embedder, progress=None):
        """Full rebuild: chunk + embed every eligible indexed file. Returns
        (files, chunks). `progress(done, total)` is called every batch."""
        if not self.ready:
            return 0, 0
        with self.lock:
            if self.dim:
                self._fresh_index(self.dim)
        records = list(store.metadata.values())
        total = len(records)
        files_with_chunks = 0
        total_chunks = 0
        for i, record in enumerate(records):
            from ..watcher.snapshot_store import norm_key
            key = norm_key(record.get("path", ""))
            if self.index_file(key, record, embedder):
                files_with_chunks += 1
                total_chunks += len(self.path_to_id.get(key, []))
            if progress and (i + 1) % 200 == 0:
                progress(i + 1, total)
        self.built_at = time.time()
        self.save()
        return files_with_chunks, total_chunks

    def remove_file(self, file_key):
        """Drop every chunk belonging to one file. Renames/moves reuse this:
        remove under the old key, then index_file under the new one."""
        with self.lock:
            ids = self.path_to_id.pop(file_key, None)
            if not ids or self.index is None:
                return False
            for chunk_id in ids:
                self.metadata.pop(chunk_id, None)
            self.index.remove_ids(np.array(sorted(ids), dtype="int64"))
            return True

    def rename_file(self, old_key, new_key, record, embedder):
        self.remove_file(old_key)
        return self.index_file(new_key, record, embedder)

    def search(self, query_vec, k=50):
        """Hits are {score, file_key, path, name, snippet} — not records."""
        with self.lock:
            if not self.ready or self.index is None or self.index.ntotal == 0:
                return []
            k = min(k, self.index.ntotal)
            scores, ids = self.index.search(
                np.asarray(query_vec, dtype="float32").reshape(1, -1), k
            )
            hits = []
            for score, chunk_id in zip(scores[0], ids[0]):
                chunk_id = int(chunk_id)
                if chunk_id == -1:
                    continue
                meta = self.metadata.get(chunk_id)
                if meta is None:
                    continue
                hits.append({
                    "score": float(score),
                    "file_key": meta["file_key"],
                    "path": meta.get("path"),
                    "name": meta.get("name"),
                    "snippet": meta.get("snippet", ""),
                })
            return hits

    def _next_id(self):
        ids = list(self.metadata.keys())
        return (max(ids) + 1) if ids else 1

    def save(self):
        with self.lock:
            if self.index is None:
                return
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, str(self.index_path))
            payload = {
                "dim": self.dim,
                "built_at": self.built_at,
                "enabled": self.enabled,
                "ids": sorted(self.metadata.keys()),
                "path_to_id": self.path_to_id,
                "metadata": {str(k): v for k, v in self.metadata.items()},
            }
            tmp = self.meta_path.with_name(self.meta_path.name + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.meta_path)

    def load(self):
        with self.lock:
            if not self.index_path.exists() or not self.meta_path.exists():
                return False
            try:
                self.index = faiss.read_index(str(self.index_path))
                payload = json.loads(self.meta_path.read_text(encoding="utf-8"))
                self.dim = payload.get("dim", self.index.d)
                self.built_at = payload.get("built_at")
                self.enabled = bool(payload.get("enabled"))
                self.metadata = {int(k): v for k, v in payload.get("metadata", {}).items()}
                self.path_to_id = {k: list(v) for k, v in payload.get("path_to_id", {}).items()}
                return True
            except Exception:
                self.index = None
                self.metadata = {}
                self.path_to_id = {}
                return False

    def stats(self):
        with self.lock:
            return {
                "enabled": self.enabled,
                "chunks": self.index.ntotal if self.index is not None else 0,
                "files": len(self.path_to_id),
                "built_at": self.built_at,
            }

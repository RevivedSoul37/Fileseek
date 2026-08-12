import json
import threading
import time
from pathlib import Path

import faiss
import numpy as np

from ..core.config import INDEX_DIR, INDEX_PATH, METADATA_PATH


class IndexStore:
    def __init__(self):
        self.index = None
        self.metadata = {}
        self.path_to_id = {}
        self.built_at = None
        self.last_indexed = None
        self.dim = None
        self.lock = threading.RLock()

    def is_ready(self):
        return self.index is not None and len(self.metadata) > 0

    def build(self, records, embeddings):
        with self.lock:
            if len(records) != len(embeddings):
                raise ValueError("records and embeddings length mismatch")
            keys = list(records.keys())
            dim = embeddings.shape[1] if len(embeddings) else 384
            self.dim = dim
            flat = faiss.IndexFlatIP(dim)
            self.index = faiss.IndexIDMap(flat)
            ids = np.arange(1, len(keys) + 1, dtype="int64")
            if len(keys):
                self.index.add_with_ids(embeddings, ids)
            self.metadata = {}
            self.path_to_id = {}
            for key_id, key in zip(ids, keys):
                self.metadata[int(key_id)] = records[key]
                self.path_to_id[key] = int(key_id)
            self.built_at = time.time()
            self.last_indexed = time.time()

    def add_or_update(self, key, record, embedding):
        with self.lock:
            if self.index is None:
                return False
            embedding = np.asarray(embedding, dtype="float32").reshape(1, -1)
            existing_id = self.path_to_id.get(key)
            if existing_id is not None:
                self.index.remove_ids(np.array([existing_id], dtype="int64"))
                self.metadata.pop(existing_id, None)
                del self.path_to_id[key]
            new_id = self._next_id()
            self.index.add_with_ids(embedding, np.array([new_id], dtype="int64"))
            self.metadata[new_id] = record
            self.path_to_id[key] = new_id
            self.last_indexed = time.time()
            return True

    def remove(self, key):
        with self.lock:
            if self.index is None:
                return False
            existing_id = self.path_to_id.get(key)
            if existing_id is None:
                return False
            self.index.remove_ids(np.array([existing_id], dtype="int64"))
            self.metadata.pop(existing_id, None)
            del self.path_to_id[key]
            self.last_indexed = time.time()
            return True

    def _next_id(self):
        ids = list(self.metadata.keys())
        return max(ids) + 1 if ids else 1

    def search(self, query_embedding, k=20):
        with self.lock:
            if self.index is None or self.index.ntotal == 0:
                return []
            k = min(k, self.index.ntotal)
            scores, result_ids = self.index.search(
                np.asarray(query_embedding, dtype="float32").reshape(1, -1), k
            )
            hits = []
            for score, result_id in zip(scores[0], result_ids[0]):
                result_id = int(result_id)
                if result_id == -1:
                    continue
                record = self.metadata.get(result_id)
                if record is None:
                    continue
                hits.append({"score": float(score), "record": record})
            return hits

    def save(self, path=None, metadata_path=None):
        with self.lock:
            if self.index is None:
                return
            index_path = Path(path or INDEX_PATH)
            meta_path = Path(metadata_path or METADATA_PATH)
            INDEX_DIR.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, str(index_path))
            payload = {
                "dim": self.dim,
                "built_at": self.built_at,
                "last_indexed": self.last_indexed,
                "ids": sorted(int(m) for m in self.metadata.keys()),
                "path_to_id": self.path_to_id,
                "metadata": {str(k): v for k, v in self.metadata.items()},
            }
            meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    def load(self, path=None, metadata_path=None):
        with self.lock:
            index_path = Path(path or INDEX_PATH)
            meta_path = Path(metadata_path or METADATA_PATH)
            if not index_path.exists() or not meta_path.exists():
                return False
            try:
                self.index = faiss.read_index(str(index_path))
                payload = json.loads(meta_path.read_text(encoding="utf-8"))
                self.dim = payload.get("dim", self.index.d)
                self.built_at = payload.get("built_at")
                self.last_indexed = payload.get("last_indexed")
                self.metadata = {int(k): v for k, v in payload.get("metadata", {}).items()}
                self.path_to_id = payload.get("path_to_id", {})
                return True
            except Exception:
                self.index = None
                self.metadata = {}
                self.path_to_id = {}
                return False

    def stats(self):
        with self.lock:
            count = len(self.metadata) if self.metadata else 0
            categories = {}
            for record in self.metadata.values():
                categories[record.get("category", "other")] = categories.get(record.get("category", "other"), 0) + 1
            return {
                "file_count": count,
                "ready": self.is_ready(),
                "last_indexed": self.last_indexed,
                "built_at": self.built_at,
                "dimensions": self.dim,
                "categories": categories,
            }

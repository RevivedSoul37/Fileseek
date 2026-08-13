import hashlib
import json
import os
import threading
import time
from pathlib import Path

from ..core.config import DIFF_MAX_BYTES, DIFF_MAX_LINES, SNAPSHOT_MAX_HASH_BYTES, SNAPSHOT_PATH
from ..core.utils import decode_excerpt

_CHUNK = 1024 * 1024


def norm_key(path):
    return str(path).lower()


class SnapshotStore:
    """Keeps just enough 'before' state to diff against - a content hash and,
    for text files only, a capped excerpt. Not a version history."""

    def __init__(self, path=None):
        self.path = Path(path or SNAPSHOT_PATH)
        self.snapshots = {}
        self.lock = threading.RLock()

    def load(self):
        with self.lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                self.snapshots = payload.get("snapshots", {})
                return True
            except (OSError, ValueError):
                self.snapshots = {}
                return False

    def save(self):
        with self.lock:
            if not self.snapshots:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"saved_at": time.time(), "snapshots": self.snapshots}
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def get(self, path):
        with self.lock:
            return self.snapshots.get(norm_key(path))

    def put(self, path, snapshot, overwrite=True):
        with self.lock:
            key = norm_key(path)
            if not overwrite and key in self.snapshots:
                return False
            self.snapshots[key] = snapshot
            return True

    def remove(self, path):
        with self.lock:
            return self.snapshots.pop(norm_key(path), None) is not None

    def rename(self, old_path, new_path):
        with self.lock:
            snap = self.snapshots.pop(norm_key(old_path), None)
            if snap is not None:
                self.snapshots[norm_key(new_path)] = snap
            return snap is not None

    def rename_prefix(self, old_dir, new_dir):
        old_prefix = norm_key(old_dir).rstrip(os.sep) + os.sep
        new_prefix = norm_key(new_dir).rstrip(os.sep) + os.sep
        with self.lock:
            moved = 0
            for key in [k for k in self.snapshots if k.startswith(old_prefix)]:
                self.snapshots[new_prefix + key[len(old_prefix):]] = self.snapshots.pop(key)
                moved += 1
            return moved

    def remove_prefix(self, dir_path):
        prefix = norm_key(dir_path).rstrip(os.sep) + os.sep
        with self.lock:
            victims = [k for k in self.snapshots if k.startswith(prefix)]
            for key in victims:
                del self.snapshots[key]
            return len(victims)

    def snapshot_file(self, path):
        """Read `path` once; return {"hash", "size", "modified", "text"} where
        text is a capped excerpt (None for binary/unreadable files), or None
        if the file cannot be read at all. Hashing stops at
        SNAPSHOT_MAX_HASH_BYTES so very large files cannot stall the watcher;
        'truncated' marks such snapshots so change detection also compares
        size and mtime."""
        try:
            stat = os.stat(path)
            size = stat.st_size
        except OSError:
            return None
        hasher = hashlib.sha256()
        head = b""
        hashed = 0
        truncated = False
        try:
            with open(path, "rb") as fh:
                while hashed < SNAPSHOT_MAX_HASH_BYTES:
                    chunk = fh.read(min(_CHUNK, SNAPSHOT_MAX_HASH_BYTES - hashed))
                    if not chunk:
                        break
                    hasher.update(chunk)
                    hashed += len(chunk)
                    if len(head) < DIFF_MAX_BYTES:
                        head += chunk
                truncated = hashed < size
        except OSError:
            return None
        text = decode_excerpt(head[:DIFF_MAX_BYTES])
        if text is not None:
            lines = text.splitlines()
            if len(lines) > DIFF_MAX_LINES:
                text = "\n".join(lines[:DIFF_MAX_LINES])
        return {
            "hash": hasher.hexdigest(),
            "size": size,
            "modified": stat.st_mtime,
            "text": text,
            "truncated": truncated,
        }

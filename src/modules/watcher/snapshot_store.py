import hashlib
import os
import sqlite3
import threading
import time
from pathlib import Path

from ..core.config import (
    DIFF_MAX_BYTES,
    DIFF_MAX_LINES,
    SNAPSHOT_DB_PATH,
    SNAPSHOT_MAX_HASH_BYTES,
)
from ..core.utils import decode_excerpt

_CHUNK = 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    file_key   TEXT PRIMARY KEY,
    hash       TEXT NOT NULL,
    size       INTEGER NOT NULL,
    modified   REAL NOT NULL,
    text       TEXT,
    truncated  INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);
"""


def norm_key(path):
    return os.path.normpath(str(path)).lower()


class SnapshotStore:
    """SQLite card drawer of per-file snapshots: one row per watched file
    carrying its hash, size, mtime and a capped text excerpt (the 'before'
    copy the change-diff stamps compare against).

    Replaces the retired whole-file JSON store (data/snapshots.json): writes
    touch ONE row per event and commit immediately; startup opens the drawer
    lazily instead of parsing hundreds of MB; the text cap is DIFF_MAX_BYTES
    (64 KB) instead of 512 KB. The public API (get/put/remove/rename/
    rename_prefix/snapshot_file/save/load) is unchanged so sync.py and the
    verify suite keep working as-is."""

    def __init__(self, path=None):
        self.path = Path(path or SNAPSHOT_DB_PATH)
        self._conn = None
        self.lock = threading.RLock()

    def _open(self):
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
        return self._conn

    def close(self):
        with self.lock:
            if self._conn is not None:
                self._conn.commit()
                self._conn.close()
                self._conn = None

    def __len__(self):
        with self.lock:
            row = self._open().execute("SELECT COUNT(*) FROM snapshots").fetchone()
            return int(row[0])

    def legacy_json_path(self):
        """The retired whole-file store that used to live next to us."""
        return self.path.with_name(self.path.stem + ".json")

    def retired_legacy_path(self):
        return Path(str(self.legacy_json_path()) + ".retired")

    def load(self):
        """Lazy startup: open the drawer and retire the legacy JSON store in
        one rename (seeding refills the drawer in the background and deletes
        the retired copy when done)."""
        with self.lock:
            self._open()
            legacy = self.legacy_json_path()
            if legacy.exists() and legacy.resolve() != self.path.resolve():
                try:
                    legacy.replace(self.retired_legacy_path())
                except OSError:
                    pass
            return True
    def get(self, path):
        with self.lock:
            row = self._open().execute(
                "SELECT hash, size, modified, text, truncated"
                " FROM snapshots WHERE file_key = ?",
                (norm_key(path),),
            ).fetchone()
        if row is None:
            return None
        return {
            "hash": row[0],
            "size": row[1],
            "modified": row[2],
            "text": row[3],
            "truncated": bool(row[4]),
        }

    def put(self, path, snapshot, overwrite=True):
        with self.lock:
            conn = self._open()
            key = norm_key(path)
            if not overwrite:
                if conn.execute(
                    "SELECT 1 FROM snapshots WHERE file_key = ?", (key,)
                ).fetchone():
                    return False
            conn.execute(
                "INSERT OR REPLACE INTO snapshots"
                " (file_key, hash, size, modified, text, truncated, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, snapshot["hash"], snapshot["size"], snapshot["modified"],
                 snapshot.get("text"), int(bool(snapshot.get("truncated"))),
                 time.time()),
            )
            conn.commit()
            return True

    def remove(self, path):
        with self.lock:
            conn = self._open()
            cur = conn.execute(
                "DELETE FROM snapshots WHERE file_key = ?", (norm_key(path),)
            )
            conn.commit()
            return cur.rowcount > 0

    def rename(self, old_path, new_path):
        with self.lock:
            snap = self.get(old_path)
            if snap is None:
                return False
            self.remove(old_path)
            return self.put(new_path, snap)

    def rename_prefix(self, old_dir, new_dir):
        """Range scan instead of LIKE: file keys may contain underscores and
        LIKE would treat those as wildcards."""
        with self.lock:
            conn = self._open()
            old_prefix = norm_key(old_dir).rstrip(os.sep) + os.sep
            new_prefix = norm_key(new_dir).rstrip(os.sep) + os.sep
            hi = old_prefix[:-1] + chr(ord(old_prefix[-1]) + 1)
            rows = conn.execute(
                "SELECT file_key, hash, size, modified, text, truncated"
                " FROM snapshots WHERE file_key >= ? AND file_key < ?",
                (old_prefix, hi),
            ).fetchall()
            moved = 0
            for row in rows:
                key = row[0]
                if not key.startswith(old_prefix):
                    continue
                snap = {"hash": row[1], "size": row[2], "modified": row[3],
                        "text": row[4], "truncated": bool(row[5])}
                conn.execute("DELETE FROM snapshots WHERE file_key = ?", (key,))
                conn.execute(
                    "INSERT OR REPLACE INTO snapshots"
                    " (file_key, hash, size, modified, text, truncated, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (new_prefix + key[len(old_prefix):], row[1], row[2], row[3],
                     row[4], row[5], time.time()),
                )
                moved += 1
            conn.commit()
            return moved
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

    def save(self):
        """Every put/remove already commits; save() just flushes + compacts
        when the retired legacy store is still lying around post-seed."""
        with self.lock:
            conn = self._open()
            conn.commit()
            retired = self.retired_legacy_path()
            if retired.exists() and len(self) > 0:
                try:
                    retired.unlink()
                except OSError:
                    pass

    def stats(self):
        with self.lock:
            row = self._open().execute(
                "SELECT COUNT(*), COALESCE(SUM(LENGTH(text)), 0) FROM snapshots"
            ).fetchone()
            return {"entries": int(row[0]), "text_bytes": int(row[1])}
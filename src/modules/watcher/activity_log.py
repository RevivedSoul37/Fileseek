import json
import threading
import time
from pathlib import Path

from ..core.config import ACTIVITY_MAX_ENTRIES, ACTIVITY_PATH


class ActivityLog:
    """Capped in-memory ring of applied watcher events, persisted next to the
    index as data/activity.json (atomic tmp-replace like snapshot_store.save).

    Entry shape: {"ts": epoch, "kind": created|modified|deleted|moved|moved_dir,
    "name": display name, "from": source (moves), "to": destination (moves),
    "diff_summary": human change stamp when available}."""

    def __init__(self, path=None, max_entries=None):
        self.path = Path(path or ACTIVITY_PATH)
        self.max_entries = max_entries or ACTIVITY_MAX_ENTRIES
        self.entries = []
        self.lock = threading.RLock()

    def load(self):
        """Best-effort restore; a missing or corrupt file starts empty."""
        with self.lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                entries = payload.get("entries", [])
                if not isinstance(entries, list):
                    entries = []
                self.entries = entries[-self.max_entries:]
                return True
            except (OSError, ValueError):
                self.entries = []
                return False

    def save(self):
        with self.lock:
            if not self.entries:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"saved_at": time.time(), "entries": self.entries}
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def append(self, entry):
        """Append newest-last; enforce the cap by dropping the oldest."""
        with self.lock:
            entry = dict(entry)
            entry.setdefault("ts", time.time())
            self.entries.append(entry)
            overflow = len(self.entries) - self.max_entries
            if overflow > 0:
                del self.entries[:overflow]
            return entry

    def append_batch(self, events):
        """Bulk append from a sync pass, keeping the ring cap."""
        if not events:
            return 0
        with self.lock:
            now = time.time()
            for i, event in enumerate(events):
                entry = dict(event)
                entry.setdefault("ts", now + i * 1e-9)
                self.entries.append(entry)
            overflow = len(self.entries) - self.max_entries
            if overflow > 0:
                del self.entries[:overflow]
            return len(events)

    def newest_first(self, limit=None):
        """Newest-first view; the API and the drawer both want this order."""
        with self.lock:
            if limit and limit > 0:
                return list(reversed(self.entries[-limit:]))
            return list(reversed(self.entries))

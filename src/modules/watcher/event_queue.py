import threading
import time
from collections import deque

from ..core.config import WATCH_DEBOUNCE_SECONDS, WATCH_MAX_BATCH_SECONDS


class EventQueue:
    """Collects rapid-fire file system events and batches them per path, so a
    burst of N saves in one second becomes one 'modified' entry per file.

    Event payloads are dicts with at least {"type", "path"}. Move events carry
    {"type": "moved", "src_path", "path"}. Batching rules per path key:
      - a create then a modify stays 'created' (we index once at flush)
      - repeated modifies collapse to one 'modified'
      - a create then a delete cancels out entirely
      - a modify then a delete keeps only 'deleted'
      - a delete then a create becomes 'created' (re-add)
      - moves onto the same destination keep the newest move only
    """

    def __init__(self, debounce_seconds=None, max_batch_seconds=None):
        self.debounce = debounce_seconds if debounce_seconds is not None else WATCH_DEBOUNCE_SECONDS
        self.max_batch = max_batch_seconds if max_batch_seconds is not None else WATCH_MAX_BATCH_SECONDS
        self.pending = {}
        self.arrival_order = deque()
        self._last_event_at = time.monotonic()
        self._first_event_at = None
        self.lock = threading.Lock()
        self.wakeup = threading.Event()

    def _merge(self, old, new):
        ot, nt = old["type"], new["type"]
        if nt == "deleted":
            if ot == "created":
                return None
            return {"type": "deleted", "path": old["path"]}
        if nt == "moved":
            if ot == "created":
                return {"type": "created", "path": new["path"]}
            return new
        if nt == "modified":
            if ot in ("created", "moved"):
                return old
            return new
        return new

    def push(self, event):
        now = time.monotonic()
        path = event["path"]
        with self.lock:
            existing = self.pending.get(path)
            if existing is None:
                self.pending[path] = event
                self.arrival_order.append(path)
            else:
                merged = self._merge(existing, event)
                if merged is None:
                    del self.pending[path]
                    if path in self.arrival_order:
                        self.arrival_order.remove(path)
                else:
                    self.pending[path] = merged
            self._last_event_at = now
            if self._first_event_at is None:
                self._first_event_at = now
            should_flush = (
                len(self.pending) >= 200
                or now - self._first_event_at >= self.max_batch
            )
        if should_flush:
            self.wakeup.set()
        return event

    def flush(self):
        """Return the current batch as a list and reset internal state."""
        with self.lock:
            if not self.pending:
                self.wakeup.clear()
                return []
            batch = [self.pending[k] for k in self.arrival_order if k in self.pending]
            self.pending.clear()
            self.arrival_order.clear()
            self._first_event_at = None
            self.wakeup.clear()
        return batch

    def drain_due_events(self):
        """Return the batch now if enough quiet time has passed since the last
        event (or the batch hit its max age); otherwise return []."""
        with self.lock:
            if not self.pending:
                return []
            now = time.monotonic()
            quiet_for = now - self._last_event_at
            age = now - (self._first_event_at or now)
            if quiet_for < self.debounce and age < self.max_batch:
                return []
        return self.flush()

    def is_idle(self):
        with self.lock:
            return not self.pending

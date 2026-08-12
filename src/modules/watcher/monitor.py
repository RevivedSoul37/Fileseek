import logging
import os
import threading
import time
from pathlib import PurePath

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..core.config import (
    EXCLUDE_DIR_NAMES,
    EXCLUDE_PATHS,
    INDEX_DIR,
    SCAN_DIRS,
    WATCH_SAVE_INTERVAL_SECONDS,
)
from .event_queue import EventQueue
from .snapshot_store import SnapshotStore
from .sync import Sync

log = logging.getLogger("fileseek.watcher")


def is_excluded_path(path):
    try:
        resolved = os.path.normpath(path).lower()
    except OSError:
        return True
    if resolved.startswith(str(INDEX_DIR).lower()):
        return True
    for excluded in EXCLUDE_PATHS:
        if resolved.startswith(excluded.lower()):
            return True
    for part in PurePath(path).parts:
        if part.lower() in EXCLUDE_DIR_NAMES:
            return True
    return False


class FileEventHandler(FileSystemEventHandler):
    """Translates watchdog events into small per-file entries pushed onto the
    EventQueue. The OS-level watch is recursive; junk folders are dropped here
    by path check rather than by scheduling separate watches."""

    def __init__(self, queue):
        self.queue = queue

    def on_created(self, event):
        if event.is_directory or is_excluded_path(event.src_path):
            return
        self.queue.push({"type": "created", "path": event.src_path})

    def on_modified(self, event):
        if event.is_directory or is_excluded_path(event.src_path):
            return
        self.queue.push({"type": "modified", "path": event.src_path})

    def on_deleted(self, event):
        if event.is_directory or is_excluded_path(event.src_path):
            return
        self.queue.push({"type": "deleted", "path": event.src_path})

    def on_moved(self, event):
        if event.is_directory:
            self.queue.push({
                "type": "moved_dir",
                "src_path": event.src_path,
                "path": event.dest_path,
            })
            return
        if is_excluded_path(event.dest_path):
            self.queue.push({"type": "deleted", "path": event.src_path})
            return
        self.queue.push({
            "type": "moved",
            "src_path": event.src_path,
            "path": event.dest_path,
        })


def create_observer():
    observer = Observer()
    observer.daemon = True
    return observer


class WatcherService:
    """Owns the watchdog observer, the debouncing queue, and the sync loop.
    start() schedules one recursive watch per scan dir; a daemon thread drains
    the queue and applies batches via Sync."""

    def __init__(self, store, embedder, snapshot_path=None):
        self.store = store
        self.snapshots = SnapshotStore(snapshot_path)
        self.queue = EventQueue()
        self.sync = Sync(store, embedder, self.snapshots)
        self.observer = None
        self._thread = None
        self._stop = threading.Event()
        self._running = False

    @property
    def running(self):
        return self._running

    def seed_snapshots(self):
        """First run only: snapshot every file currently in the index so later
        changes produce real line diffs. Expensive (hashes up to 13k files),
        so it runs in a background thread and is skipped if snapshots.json
        already exists. Files that change mid-seed are handled correctly by
        sync (they fall back to a size-delta diff for that first change)."""
        if self.snapshots.path.exists():
            self.snapshots.load()
            log.info("Snapshots loaded (%d entries)", len(self.snapshots.snapshots))
            return None

        def _seed():
            records = list(self.store.metadata.values())
            count = 0
            for record in records:
                path = record.get("path")
                if not path or self._stop.is_set():
                    break
                snapshot = self.snapshots.snapshot_file(path)
                if snapshot is None:
                    continue
                if self.snapshots.put(path, snapshot, overwrite=False):
                    count += 1
            if not self._stop.is_set():
                self.snapshots.save()
                log.info("Snapshots seeded for %d files", count)

        thread = threading.Thread(target=_seed, daemon=True)
        thread.start()
        log.info("Snapshot seeding started in background (%d files)",
                 len(self.store.metadata))
        return thread

    def start(self):
        if self._running:
            return False
        self._stop.clear()
        self.observer = create_observer()
        handler = FileEventHandler(self.queue)
        watched = 0
        for root in SCAN_DIRS:
            if not os.path.isdir(root):
                continue
            self.observer.schedule(handler, root, recursive=True)
            watched += 1
        if watched == 0:
            return False
        self.observer.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._running = True
        log.info("Watcher running on %d folder(s), debounce %.1fs",
                 watched, self.queue.debounce)
        return True

    def _save(self):
        self.store.save()
        self.snapshots.save()

    def _loop(self):
        last_save = time.monotonic()
        dirty = False
        while not self._stop.is_set():
            batch = self.queue.drain_due_events()
            if batch:
                applied = self.sync.handle_batch(batch)
                if applied:
                    dirty = True
                    log.info("Watcher applied %d change(s)", applied)
            since_save = time.monotonic() - last_save
            flush = dirty and (
                self.sync.changes_since_save >= 10
                or since_save >= WATCH_SAVE_INTERVAL_SECONDS
            )
            if flush:
                self._save()
                dirty = False
                last_save = time.monotonic()
                log.info("Watcher saved index (%d change(s))",
                         self.sync.changes_since_save)
                self.sync.mark_saved()
            self._stop.wait(0.2)
        pending = self.queue.flush()
        if pending:
            self.sync.handle_batch(pending)
        if dirty or pending:
            self._save()
            log.info("Watcher saved final state on shutdown")

    def stop(self):
        if not self._running:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        if self.observer is not None:
            self.observer.stop()
            self.observer.join(timeout=3)
        self._running = False
        log.info("Watcher stopped")

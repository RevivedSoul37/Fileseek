import logging
import os
import threading

from ..indexer.crawler import build_record
from .diff import size_only_fields, summarize_diff
from .snapshot_store import norm_key

log = logging.getLogger("fileseek.watcher")


class Sync:
    """Applies batched file system events to the FAISS index and the snapshot
    store. Content-only modifications are metadata-only updates (no re-embed:
    embeddings are built from name+folder+type, which content edits do not
    change), while creates, moves and renames re-embed as needed."""

    def __init__(self, store, embedder, snapshots, activity=None, content_index=None):
        self.store = store
        self.embedder = embedder
        self.snapshots = snapshots
        self.activity = activity
        self.content_index = content_index
        self.lock = threading.Lock()
        self.changes_since_save = 0

    def _embed_one(self, record):
        text = self.embedder.build_text(record)
        return self.embedder.embed_query(text)

    def _content_upsert(self, record):
        """Keep the content index in step with the name index (no-op when the
        feature flag is off: ContentIndex.ready stays False)."""
        if self.content_index is None or not self.content_index.ready:
            return False
        return bool(self.content_index.index_file(norm_key(record["path"]), record, self.embedder))

    def _content_remove(self, path):
        if self.content_index is None or not self.content_index.ready:
            return False
        return self.content_index.remove_file(norm_key(path))

    def _activity_entry(self, event):
        """One feed entry per applied event. `from`/`to` only appear on moves;
        `diff_summary` only when the index recorded one."""
        etype = event["type"]
        path = event.get("path", "")
        entry = {"kind": etype, "name": os.path.basename(path) or path}
        if etype in ("moved", "moved_dir"):
            src = event.get("src_path", "")
            if etype == "moved_dir":
                entry["name"] = os.path.basename(event.get("path", "")) or event.get("path", "")
            entry["from"] = os.path.basename(src) or src
            entry["to"] = os.path.basename(path) or path
        if etype == "modified":
            record = self.store.get_record(norm_key(path))
            if record and record.get("last_diff_summary"):
                entry["diff_summary"] = record["last_diff_summary"]
        return entry

    def handle_batch(self, batch):
        if not batch:
            return 0
        with self.lock:
            applied = 0
            feed = []
            for event in batch:
                try:
                    if self._apply(event):
                        applied += 1
                        if self.activity is not None:
                            feed.append(self._activity_entry(event))
                except Exception as exc:
                    log.warning("Sync event failed (%s %s): %s",
                                event.get("type"), event.get("path"), exc)
            if self.activity is not None and feed:
                self.activity.append_batch(feed)
            self.changes_since_save += applied
            return applied

    def needs_save(self):
        return self.changes_since_save >= 10

    def mark_saved(self):
        self.changes_since_save = 0

    def _apply(self, event):
        etype = event["type"]
        if etype == "created":
            return self._handle_created(event)
        if etype == "modified":
            return self._handle_modified(event)
        if etype == "deleted":
            return self._handle_deleted(event)
        if etype == "moved":
            return self._handle_moved(event)
        if etype == "moved_dir":
            return self._handle_moved_dir(event)
        return False

    def _handle_created(self, event):
        path = event["path"]
        record = build_record(path)
        if record is None:
            return False
        snapshot = self.snapshots.snapshot_file(path)
        if snapshot is not None:
            self.snapshots.put(path, snapshot)
        embedding = self._embed_one(record)
        added = self.store.add_or_update(norm_key(path), record, embedding)
        if added:
            self._content_upsert(record)
            log.info("watcher +  %s", record["name"])
        return added

    def _is_noop(self, old_snapshot, new_snapshot):
        """No-op save: content is actually identical. Plain hash equality is
        enough unless the hash was truncated (huge file), in which case size
        and mtime must also match."""
        if old_snapshot["hash"] != new_snapshot["hash"]:
            return False
        if not new_snapshot.get("truncated"):
            return True
        return (
            old_snapshot["size"] == new_snapshot["size"]
            and old_snapshot["modified"] == new_snapshot["modified"]
        )

    def _handle_modified(self, event):
        path = event["path"]
        key = norm_key(path)
        new_snapshot = self.snapshots.snapshot_file(path)
        if new_snapshot is None:
            if not os.path.isfile(path):
                return self._handle_deleted(event)
            return False
        old_snapshot = self.snapshots.get(path)
        if old_snapshot is not None and self._is_noop(old_snapshot, new_snapshot):
            old_record = self.store.get_record(key)
            if old_record is not None and old_record.get("modified") != new_snapshot["modified"]:
                old_record["modified"] = new_snapshot["modified"]
                self.store.update_record(key, old_record)
                self.snapshots.put(path, new_snapshot)
            return False

        record = build_record(path)
        if record is None:
            return False
        if old_snapshot is None:
            old_record = self.store.get_record(key)
            if old_record is None:
                return self._handle_created(event)
            diff_fields = size_only_fields(old_record.get("size"), record["size"])
        else:
            diff_fields = summarize_diff(old_snapshot, new_snapshot)
        record.update(diff_fields)
        updated = self.store.update_record(key, record)
        if updated:
            self.snapshots.put(path, new_snapshot)
            if diff_fields.get("last_diff_kind") == "text":
                self._content_upsert(record)
            log.info("watcher ~  %s (%s)", record["name"], diff_fields.get("last_diff_kind"))
        else:
            embedding = self._embed_one(record)
            updated = self.store.add_or_update(key, record, embedding)
            if updated:
                self.snapshots.put(path, new_snapshot)
                self._content_upsert(record)
        return updated

    def _handle_deleted(self, event):
        path = event["path"]
        removed = self.store.remove(norm_key(path))
        self.snapshots.remove(path)
        self._content_remove(path)
        if removed:
            log.info("watcher -  %s", os.path.basename(path))
        return removed

    def _handle_moved(self, event):
        src_path = event["src_path"]
        dest_path = event["path"]
        src_key = norm_key(src_path)
        old_record = self.store.get_record(src_key)
        record = build_record(dest_path)
        if record is None:
            return self._handle_deleted({"type": "deleted", "path": src_path})
        if old_record is not None:
            for field in ("last_diff_summary", "last_diff_lines_added",
                          "last_diff_lines_removed", "last_diff_size_delta",
                          "last_diff_kind"):
                if field in old_record:
                    record[field] = old_record[field]
        embedding = self._embed_one(record)
        self.store.remove(src_key)
        added = self.store.add_or_update(norm_key(dest_path), record, embedding)
        self.snapshots.rename(src_path, dest_path)
        if added:
            if self.content_index is not None and self.content_index.ready:
                self.content_index.rename_file(src_key, norm_key(dest_path), record, self.embedder)
            log.info("watcher -> %s", record["name"])
        return added

    def _handle_moved_dir(self, event):
        src_dir = os.path.normpath(event["src_path"])
        dest_dir = os.path.normpath(event["path"])
        src_prefix = norm_key(src_dir) + os.sep
        moved = []
        with self.store.lock:
            for key, record in list(self.store.metadata.items()):
                path = record.get("path") or ""
                if not path.lower().startswith(src_prefix):
                    continue
                old_key = self.store.path_to_id.get(path.lower())
                rel = os.path.relpath(path, src_dir)
                new_path = os.path.join(dest_dir, rel)
                moved.append((old_key, path, new_path))
        applied = 0
        for _old_id, path, new_path in moved:
            record = build_record(new_path)
            if record is None:
                continue
            embedding = self._embed_one(record)
            self.store.remove(norm_key(path))
            if self.store.add_or_update(norm_key(new_path), record, embedding):
                self._content_upsert(record)
                applied += 1
        renamed = self.snapshots.rename_prefix(src_dir, dest_dir)
        if applied:
            log.info("watcher -> folder moved: %d files, %d snapshots", applied, renamed)
        return applied > 0

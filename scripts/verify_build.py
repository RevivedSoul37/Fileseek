import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modules.core import config
from modules.core.utils import format_size, get_file_icon, get_file_category, time_ago
from modules.indexer.crawler import walk_files
from modules.indexer.embedder import Embedder
from modules.indexer.index_store import IndexStore
from modules.search.engine import SearchEngine

def check(label, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" \u2014 {detail}" if detail else ""))
    if not condition:
        sys.exit(1)

print("=== FileSeek Verification Suite ===\n")

print("-- Unit tests: utils --")
check("format_size(1048576) == '1.0 MB'", format_size(1048576) == "1.0 MB", format_size(1048576))
check("format_size(0) == '0 B'", format_size(0) == "0 B", format_size(0))
check("get_file_category('.pdf') == 'document'", get_file_category(".pdf") == "document", get_file_category(".pdf"))
check("get_file_category('.mp4') == 'media'", get_file_category(".mp4") == "media", get_file_category(".mp4"))
check("get_file_icon('.jpg') is image emoji", get_file_icon(".jpg") != "", repr(get_file_icon(".jpg")))
check("time_ago returns string", isinstance(time_ago(time.time() - 3600), str), time_ago(time.time() - 3600))

print("\n-- Crawler test --")
t0 = time.time()
records = walk_files(config.SCAN_DIRS)
elapsed = time.time() - t0
check("crawler found files", len(records) > 0, f"{len(records)} files in {elapsed:.1f}s")

sample_keys = list(records.keys())[:3]
for k in sample_keys:
    r = records[k]
    check(f"record has all fields: {r['name'][:40]}", all(f in r for f in ("name","path","parent_folder","extension","size","modified","category","icon","sensitive")))

print("\n-- Embedding test --")
embedder = Embedder(config.EMBED_MODEL_NAME)
t0 = time.time()
texts = [embedder.build_text(records[k]) for k in records]
embeddings = embedder.embed_texts(texts, batch_size=config.EMBED_BATCH_SIZE, show_progress=False)
emb_time = time.time() - t0
check("embeddings shape correct", embeddings.shape == (len(records), 384), f"{embeddings.shape} in {emb_time:.1f}s")
norms = (embeddings ** 2).sum(axis=1)
check("embeddings are L2-normalized", all(abs(n - 1.0) < 0.01 for n in norms[:100]), f"first norm={norms[0]:.4f}")

print("\n-- Index build & save --")
store = IndexStore()
store.build(records, embeddings)
check("index built", store.is_ready(), f"{store.index.ntotal} vectors")
store.save()
check("index file exists", config.INDEX_PATH.exists(), str(config.INDEX_PATH))
check("metadata file exists", config.METADATA_PATH.exists(), str(config.METADATA_PATH))

print("\n-- Index reload --")
store2 = IndexStore()
loaded = store2.load()
check("index loads from disk", loaded, f"{len(store2.metadata)} records restored")
check("metadata count matches", len(store2.metadata) == len(records), f"{len(store2.metadata)} vs {len(records)}")

print("\n-- Search tests --")
engine = SearchEngine(store2, embedder)

test_queries = [
    ("resume", "document"),
    ("video editing", "media"),
    ("cricket data", "data"),
    ("installer", "other"),
    ("python script", "code"),
]
for q, _ in test_queries:
    t0 = time.time()
    results, _ = engine.search(q, max_results=5)
    dt = (time.time() - t0) * 1000
    top = results[0]["name"] if results else "(none)"
    pct = results[0]["match_percent"] if results else 0
    check(f"search '{q}' returns results", len(results) > 0, f"top='{top}' ({pct}%) in {dt:.0f}ms, n={len(results)}")

print("\n-- Add / remove incremental test (Phase 2 readiness) --")
import numpy as np
fake_key = "c:/fake/testfile_xyz.txt"
fake_record = {"name":"testfile_xyz.txt","path":fake_key,"parent_folder":"fake","extension":".txt","size":10,"modified":time.time(),"category":"document","icon":get_file_icon(".txt"),"sensitive":False}
fake_vec = embedder.embed_query("testfile xyz")
before = store2.index.ntotal
store2.add_or_update(fake_key, fake_record, fake_vec)
check("add file increments index", store2.index.ntotal == before + 1, f"{before} -> {store2.index.ntotal}")
res, _ = engine.search("testfile_xyz", max_results=3)
check("newly added file is findable", len(res) > 0 and res[0]["name"] == "testfile_xyz.txt", res[0]["name"] if res else "not found")
store2.remove(fake_key)
check("remove file decrements index", store2.index.ntotal == before, f"{store2.index.ntotal} == {before}")

print("\n-- Category filter test --")
res_docs, _ = engine.search("resume", max_results=10, category="document")
check("category=document returns only documents", all(r["category"]=="document" for r in res_docs), f"{len(res_docs)} results")

print("\n-- Watcher: snapshot store + diff --")
import tempfile
from modules.watcher.snapshot_store import SnapshotStore, norm_key
from modules.watcher.diff import summarize_diff, size_only_fields
from modules.watcher.sync import Sync
from modules.search.ranker import record_to_result

tmp_dir = tempfile.mkdtemp(prefix="fileseek_watcher_test_")
test_file = Path(tmp_dir) / "note.txt"
test_file.write_bytes(b"line one\nline two\n")

snap = SnapshotStore(path=Path(tmp_dir) / "snaps.json")
s1 = snap.snapshot_file(str(test_file))
check("snapshot returns hash+text", s1 is not None and s1["text"] == "line one\nline two\n", repr(s1.get("text"))[:60])
snap.put(str(test_file), s1)
check("snapshot store get round-trips", snap.get(str(test_file))["hash"] == s1["hash"])

test_file.write_bytes(b"line one\nline two CHANGED\nline three\n")
s2 = snap.snapshot_file(str(test_file))
diff_fields = summarize_diff(s1, s2)
check("diff counts added lines", diff_fields["last_diff_lines_added"] == 2, str(diff_fields))
check("diff counts removed lines", diff_fields["last_diff_lines_removed"] == 1, str(diff_fields))
check("diff summary is readable", diff_fields["last_diff_summary"] == "2 lines added \u00b7 1 line removed", diff_fields["last_diff_summary"])
check("binary fallback has no lines", size_only_fields(100, 140)["last_diff_lines_added"] == 0)

print("\n-- Watcher: sync applies diff to index --")
sync_store = IndexStore()
sync_store.build({fake_key: fake_record}, embedder.embed_query("testfile xyz").reshape(1, -1))
sync = Sync(sync_store, embedder, snap)
check("update_record exists for metadata-only changes", sync_store.update_record(fake_key, {**fake_record, "sensitive": True}))
check("modified event produces diff record", sync.handle_batch([{"type": "modified", "path": str(test_file)}]) == 1)
rec = sync_store.get_record(norm_key(str(test_file)))
check("diff fields written into record", rec is not None and rec.get("last_diff_summary") == "2 lines added \u00b7 1 line removed", str(rec.get("last_diff_summary")) if rec else None)

print("\n-- record_to_result exposes diff fields --")
result = record_to_result(rec)
check("API result carries last_diff_summary", result.get("last_diff_summary") == "2 lines added \u00b7 1 line removed")

import shutil
shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n=== ALL CHECKS PASSED ===")
stats = store2.stats()
print(f"Index stats: {stats['file_count']} files, dims={stats['dimensions']}, categories={stats['categories']}")

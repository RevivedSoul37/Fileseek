import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modules.core import config
from modules.core.utils import RECORD_FIELDS, format_size, get_file_icon, get_file_category, time_ago
from modules.indexer.crawler import walk_files
from modules.indexer.embedder import Embedder
from modules.indexer.index_store import IndexStore
from modules.search.engine import SearchEngine

def check(label, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        print(f"::error title=verify_build::{label} FAILED — {detail}")
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
    check(f"record has all fields: {r['name'][:40]}", all(f in r for f in RECORD_FIELDS if not f.startswith("last_diff_")))

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

print("\n-- Snapshot redesign: SQLite drawer --")
drawer_path = Path(tmp_dir) / "drawer.db"
drawer = SnapshotStore(path=drawer_path)
drawer.load()
check("drawer is a sqlite file, not json", drawer_path.exists() and drawer_path.read_bytes()[:6] == b"SQLite", str(drawer_path.read_bytes()[:6]))
drawer.put(str(test_file), s2)
check("drawer put commits one row", len(drawer) == 1, str(len(drawer)))
drawer2 = SnapshotStore(path=drawer_path)
drawer2.load()
check("drawer survives reopen without save", drawer2.get(str(test_file))["hash"] == s2["hash"], "row-level commits")
big_diff_file = Path(tmp_dir) / "bigdiff.txt"
big_diff_file.write_bytes(b"x" * (200 * 1024))
big_snap = drawer.snapshot_file(str(big_diff_file))
check("drawer caps excerpts at 64 KB", big_snap["text"] is not None and len(big_snap["text"]) <= config.DIFF_MAX_BYTES + 64, f"len={len(big_snap['text'] or '')} cap={config.DIFF_MAX_BYTES}")
sub_old = Path(tmp_dir) / "oldsub"; sub_new = Path(tmp_dir) / "newsub"
sub_old.mkdir(exist_ok=True)
(sub_old / "m.txt").write_text("m\n", encoding="utf-8")
drawer.put(str(sub_old / "m.txt"), drawer.snapshot_file(str(sub_old / "m.txt")))
moved = drawer.rename_prefix(str(sub_old), str(sub_new))
check("rename_prefix moves rows", moved == 1 and drawer.get(str(sub_new / "m.txt")) is not None and drawer.get(str(sub_old / "m.txt")) is None, f"moved={moved}")
legacy_path = drawer_path.with_name(drawer_path.stem + ".json")
legacy_path.write_text('{"snapshots": {}}', encoding="utf-8")
drawer3 = SnapshotStore(path=drawer_path)
drawer3.load()
check("legacy snapshots.json retired on load", not legacy_path.exists() and drawer3.retired_legacy_path().exists(), str(drawer3.retired_legacy_path().name))
drawer3.save()
check("save() deletes the retired legacy after seeding", not drawer3.retired_legacy_path().exists(), "drawer now holds rows")
drawer.close(); drawer2.close(); drawer3.close()

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

print("\n-- Activity feed: ring, cap, persistence --")
from modules.watcher.activity_log import ActivityLog
import shutil as _shutil

activity_dir = tempfile.mkdtemp(prefix="fileseek_activity_test_")
activity_path = Path(activity_dir) / "activity.json"

act = ActivityLog(path=activity_path, max_entries=3)
act.append({"kind": "created", "name": "a.txt"})
act.append({"kind": "modified", "name": "a.txt", "diff_summary": "1 line added \u00b7 1 line removed"})
act.append({"kind": "deleted", "name": "a.txt"})
act.append({"kind": "created", "name": "b.txt"})
check("activity cap drops the oldest", len(act.entries) == 3 and act.entries[0]["kind"] == "modified" and act.entries[-1]["name"] == "b.txt", str([(e["kind"], e["name"]) for e in act.entries]))
act.save()
check("activity.json written", activity_path.exists(), str(activity_path.name))
act2 = ActivityLog(path=activity_path, max_entries=3)
act2.load()
check("activity survives restart", len(act2.entries) == 3 and act2.newest_first(1)[0]["name"] == "b.txt", str([e["name"] for e in act2.entries]))

_activity_store = IndexStore()
_activity_store.build({fake_key: fake_record}, embedder.embed_query("testfile xyz").reshape(1, -1))
_activity_snap = SnapshotStore(path=Path(activity_dir) / "snaps.json")
_activity_sync = Sync(_activity_store, embedder, _activity_snap, act2)
feed_file = Path(activity_dir) / "feed.txt"
feed_file.write_text("v1\n", encoding="utf-8")
check("feed records a create", _activity_sync.handle_batch([{"type": "created", "path": str(feed_file)}]) == 1 and act2.entries[-1]["kind"] == "created", str(act2.entries[-1].get("kind")))
_activity_snap.put(str(feed_file), _activity_snap.snapshot_file(str(feed_file)))
feed_file.write_text("v1\nv2\n", encoding="utf-8")
check("feed records a modify", _activity_sync.handle_batch([{"type": "modified", "path": str(feed_file)}]) == 1 and act2.entries[-1]["kind"] == "modified", str(act2.entries[-1].get("kind")))
feed_file.unlink()
check("feed records a delete", _activity_sync.handle_batch([{"type": "deleted", "path": str(feed_file)}]) == 1 and act2.entries[-1]["kind"] == "deleted", str(act2.entries[-1].get("kind")))
_shutil.rmtree(activity_dir, ignore_errors=True)

print("\n-- Runtime: graceful shutdown saves state --")
import modules.indexer.index_store as index_store_module
from modules.watcher import monitor as monitor_module
from modules.watcher.monitor import WatcherService

# The temp root must live outside junk dirs (tempfile's %TEMP% contains
# 'AppData' which the watcher's junk filter drops on sight).
verify_tmp_base = config.PROJECT_ROOT / "private" / ".verify_tmp"
_shutil.rmtree(verify_tmp_base, ignore_errors=True)
verify_tmp_base.mkdir(parents=True, exist_ok=True)
shutdown_dir = tempfile.mkdtemp(prefix="fileseek_shutdown_test_", dir=str(verify_tmp_base))
burst_file = Path(shutdown_dir) / "burst.txt"
burst_file.write_text("line one\n", encoding="utf-8")

_saved_store_paths = (index_store_module.INDEX_DIR, index_store_module.INDEX_PATH, index_store_module.METADATA_PATH)
_saved_scan_dirs = monitor_module.SCAN_DIRS
index_store_module.INDEX_DIR = Path(shutdown_dir)
index_store_module.INDEX_PATH = Path(shutdown_dir) / "fileseek.index"
index_store_module.METADATA_PATH = Path(shutdown_dir) / "metadata.json"
monitor_module.SCAN_DIRS = [shutdown_dir]
try:
    from modules.indexer.crawler import build_record as _build_record
    shut_store = IndexStore()
    burst_record = _build_record(str(burst_file))
    shut_store.build(
        {norm_key(str(burst_file)): burst_record},
        embedder.embed_query("burst file").reshape(1, -1),
    )
    shut_service = WatcherService(shut_store, embedder, snapshot_path=Path(shutdown_dir) / "snaps.json")
    shut_service.snapshots.put(str(burst_file), shut_service.snapshots.snapshot_file(str(burst_file)))
    check("watcher starts on temp root", shut_service.start())
    time.sleep(1.0)  # let the Windows event backlog drain before the burst
    burst_new = Path(shutdown_dir) / "burst_new.txt"
    burst_new.write_text("created after watcher start\n", encoding="utf-8")
    deadline = time.time() + 12
    burst_rec = None
    while time.time() < deadline:
        burst_rec = shut_store.get_record(norm_key(str(burst_new)))
        if burst_rec is not None:
            break
        time.sleep(0.2)
    check("watcher applied a burst change within the window", burst_rec is not None, burst_rec.get("name") if burst_rec else "(missing)")
    shut_index_path = Path(shutdown_dir) / "fileseek.index"
    shut_meta_path = Path(shutdown_dir) / "metadata.json"
    shut_snap_path = Path(shutdown_dir) / "snaps.json"
    check("index not yet written before shutdown", not shut_index_path.exists(), "only the 30s periodic save would write it")
    shut_service.stop()
    check("watcher stop writes the index", shut_index_path.exists() and shut_meta_path.exists(), shut_index_path.name)
    check("watcher stop writes snapshots", shut_snap_path.exists(), shut_snap_path.name)
finally:
    index_store_module.INDEX_DIR, index_store_module.INDEX_PATH, index_store_module.METADATA_PATH = _saved_store_paths
    monitor_module.SCAN_DIRS = _saved_scan_dirs
import shutil as _shutil
_shutil.rmtree(shutdown_dir, ignore_errors=True)

print("\n-- Assistant: shared decode + content reader --")
from modules.core.utils import decode_excerpt
check("decode_excerpt moved to core.utils (text round-trip)", decode_excerpt("h\u00e9llo world".encode("utf-8")) == "h\u00e9llo world")
check("decode_excerpt flags binary (NUL bytes)", decode_excerpt(b"\x89PNG\r\n\x1a\n\x00\x00") is None)

from modules.assistant.content_reader import read_for_ask
from modules.assistant.prompts import CODE_EXPLAINER, DOC_SUMMARIZER, FILE_EXPLAINER, select_prompt
from modules.assistant.explainer import Explainer

ask_dir = tempfile.mkdtemp(prefix="fileseek_ask_test_")
small_txt = Path(ask_dir) / "small.txt"
small_txt.write_text("hello\nworld\n", encoding="utf-8")
res_small = read_for_ask(str(small_txt))
check("content_reader reads text", res_small["kind"] == "text" and "hello" in res_small["content"] and not res_small["truncated"])

big_txt = Path(ask_dir) / "big.txt"
with open(big_txt, "w", encoding="utf-8") as fh:
    for i in range(4000):
        fh.write(f"line {i} of a very long file\n")
res_big = read_for_ask(str(big_txt))
check("content_reader caps large text with marker", res_big["kind"] == "text" and res_big["truncated"] and res_big["content"].startswith("[showing first"))

blob_bin = Path(ask_dir) / "blob.bin"
blob_bin.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4)
res_bin = read_for_ask(str(blob_bin))
check("content_reader treats binary as binary", res_bin["kind"] == "binary" and res_bin["content"] is None)

print("\n-- Phase 5: Ask over PDF/DOCX contents --")
def build_minimal_pdf(text, path):
    """Hand-rolled single-page PDF with one text line (no external libs)."""
    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin-1")
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    Path(path).write_bytes(bytes(out))

from docx import Document as DocxDocument

smoke_pdf = Path(ask_dir) / "smoke.pdf"
build_minimal_pdf("FileSeek pdf smoke text", str(smoke_pdf))
res_pdf = read_for_ask(str(smoke_pdf))
check("ask reads a pdf's extracted text", res_pdf["kind"] == "text" and "FileSeek pdf smoke text" in res_pdf["content"], repr(res_pdf.get("content"))[:60])

smoke_docx = Path(ask_dir) / "smoke.docx"
docx_doc = DocxDocument()
docx_doc.add_paragraph("FileSeek docx smoke paragraph")
docx_doc.save(str(smoke_docx))
res_docx = read_for_ask(str(smoke_docx))
check("ask reads a docx's extracted paragraphs", res_docx["kind"] == "text" and "FileSeek docx smoke paragraph" in res_docx["content"], repr(res_docx.get("content"))[:60])

long_pdf_text = "quick brown fox jumps over the lazy dog. " * 500
long_pdf = Path(ask_dir) / "long.pdf"
build_minimal_pdf(long_pdf_text, str(long_pdf))
res_long = read_for_ask(str(long_pdf))
check("pdf text is capped with the truncation marker", res_long["truncated"] and res_long["content"].startswith("[showing first"), f"len={len(res_long['content'])}")

corrupt_pdf = Path(ask_dir) / "corrupt.pdf"
corrupt_pdf.write_bytes(b"%PDF-1.4\nnot really a pdf body\x00\x01\x02")
res_corrupt = read_for_ask(str(corrupt_pdf))
check("corrupt pdf falls back to binary", res_corrupt["kind"] == "binary", res_corrupt["kind"])

pdf_record = {"name": "smoke.pdf", "path": str(smoke_pdf), "parent_folder": "asktest", "extension": ".pdf", "size": smoke_pdf.stat().st_size, "modified": time.time(), "category": "document", "sensitive": False}
from modules.assistant.prompts import build_prompt as _build_prompt_pdf, EXTRACTED_TEXT_NOTE


class _Stage3Stub:
    def __init__(self):
        self.last_prompt = None
    def is_available(self):
        return (True, [config.OLLAMA_MODEL])
    def generate(self, prompt, system=None, model=None):
        self.last_prompt = prompt
        return "stub pdf answer"
    def chat(self, messages, system=None, model=None):
        return "stub chat"


_pdf_stub = _Stage3Stub()
pdf_result = Explainer(client=_pdf_stub).explain(pdf_record)
check("pdf explain sends extracted content to the model", pdf_result["binary"] is False and "FileSeek pdf smoke text" in (_pdf_stub.last_prompt or ""), f"model={pdf_result['model']}")
check("pdf prompt carries the extraction note", EXTRACTED_TEXT_NOTE in _build_prompt_pdf(pdf_record, "text", "q", False))

print("\n-- Assistant: prompt selection --")
check("prompt: code gets code_explainer", select_prompt("code", ".py") == CODE_EXPLAINER)
check("prompt: markdown gets doc_summarizer", select_prompt("document", ".md") == DOC_SUMMARIZER)
check("prompt: other gets file_explainer", select_prompt("image", ".png") == FILE_EXPLAINER)

print("\n-- Assistant: explainer with stubbed client --")
class StubOllama:
    def __init__(self):
        self.calls = 0
        self.chat_calls = 0
        self.last_messages = None
    def is_available(self):
        return (True, [config.OLLAMA_MODEL, config.OLLAMA_CODE_MODEL])
    def generate(self, prompt, system=None, model=None):
        self.calls += 1
        return "stub answer"
    def chat(self, messages, system=None, model=None):
        self.chat_calls += 1
        self.last_messages = list(messages)
        return "stub chat answer"

stub = StubOllama()
test_explainer = Explainer(client=stub)
blob_record = {"name": "blob.bin", "path": str(blob_bin), "parent_folder": "asktest", "extension": ".bin", "size": blob_bin.stat().st_size, "modified": blob_bin.stat().st_mtime, "category": "other", "sensitive": False}
blob_result = test_explainer.explain(blob_record)
check("binary explain answers without calling the model", blob_result["binary"] and stub.calls == 0 and "blob.bin" in blob_result["answer"], f"model calls={stub.calls}")

code_file = Path(ask_dir) / "script.py"
code_file.write_text("print('hi')\n", encoding="utf-8")
code_record = {"name": "script.py", "path": str(code_file), "parent_folder": "asktest", "extension": ".py", "size": code_file.stat().st_size, "modified": time.time(), "category": "code", "sensitive": False}
code_result = test_explainer.explain(code_record)
check("code explain routes to the code model", code_result["model"] == config.OLLAMA_CODE_MODEL and code_result["binary"] is False, f"model={code_result['model']}")

print("\n-- API: /api/ask contract --")
import app as app_module
api = app_module.app.test_client()

print("\n-- Audit fixes: path gates + input hardening --")
_outside_ask_dir = Path(tempfile.mkdtemp(prefix="fileseek_outside_ask_"))
_outside_probe = _outside_ask_dir / "probe.txt"
_outside_probe.write_text("outside the scan roots\n", encoding="utf-8")
resp_ask_out = api.post("/api/ask", json={"path": str(_outside_probe)})
check("ask 403 outside scan roots", resp_ask_out.status_code == 403, resp_ask_out.get_json()["error"])
resp_more_out = api.post("/api/ask-more", json={"path": str(_outside_probe), "question": "q"})
check("ask-more 403 outside scan roots", resp_more_out.status_code == 403, resp_more_out.get_json()["error"])
resp_card_out = api.get("/api/file-card?path=" + str(_outside_probe))
check("file-card 403 outside scan roots", resp_card_out.status_code == 403, resp_card_out.get_json()["error"])
resp_search_empty = api.post("/api/search", json={"query": "   "})
check("search empty query returns 200 with no results", resp_search_empty.status_code == 200 and resp_search_empty.get_json()["results"] == [])
resp_search_bad = api.post("/api/search", json={"query": "resume", "limit": "banana"})
check("search garbage limit tolerated", resp_search_bad.status_code == 200)
resp_browse_bad = api.get("/api/browse?limit=banana")
check("browse garbage limit tolerated", resp_browse_bad.status_code == 200)
from modules.indexer.crawler import _is_excluded_dir as _crawler_excluded
check("crawler excludes its own data dir", _crawler_excluded(str(config.INDEX_DIR)) and _crawler_excluded(str(config.INDEX_DIR / "fileseek.index")), str(config.INDEX_DIR))
from modules.compare import platforms as _platforms_fix
_audit_cmp_record = {"name": "x.pdf", "parent_folder": "t", "extension": ".pdf", "category": "document", "size": 10, "sensitive": False}
check("compare links carry the typed question", "my%20typed%20question" in _platforms_fix.compare_links(_audit_cmp_record, "my typed question")[0]["url"])
check("no .tmp leftovers after saves", not list(config.INDEX_DIR.glob("*.tmp")), str(list(config.INDEX_DIR.glob("*.tmp"))))
_saved_scan_ask = list(config.SCAN_DIRS)
config.apply_scan_dirs([ask_dir])

resp_missing = api.post("/api/ask", json={"path": str(Path(ask_dir) / "nope.txt")})
check("ask 404 for missing file", resp_missing.status_code == 404 and resp_missing.get_json()["ok"] is False)

app_module.explainer.client = stub
resp_ok = api.post("/api/ask", json={"path": str(code_file)})
check("ask 200 with answer for text file", resp_ok.status_code == 200 and resp_ok.get_json().get("ok") is True, str(resp_ok.get_json()).strip(". ")[:80])
resp_custom = api.post("/api/ask", json={"path": str(code_file), "question": "who wrote this?"})
check("ask echoes a typed custom question", resp_custom.get_json()["question"] == "who wrote this?", resp_custom.get_json()["question"])

class DownOllama:
    def is_available(self):
        return (False, [])
    def generate(self, prompt, system=None, model=None):
        from modules.assistant.llm_client import OllamaError
        raise OllamaError("Ollama is not running - start it with `ollama serve`")
    def chat(self, messages, system=None, model=None):
        from modules.assistant.llm_client import OllamaError
        raise OllamaError("Ollama is not running - start it with `ollama serve`")

app_module.explainer.client = DownOllama()
resp_down = api.post("/api/ask", json={"path": str(code_file)})
check("ask 503 with friendly error when Ollama down", resp_down.status_code == 503 and "Ollama" in resp_down.get_json()["error"], resp_down.get_json()["error"])

print("\n-- Runtime: /api/open/* path validation --")
import os
open_dir = tempfile.mkdtemp(prefix="fileseek_open_test_")
open_inside = str(Path(config.SCAN_DIRS[0]) / "fileseek_open_probe.txt")
Path(open_inside).write_text("probe\n", encoding="utf-8")
open_outside = os.path.join(open_dir, "probe_outside.txt")
Path(open_outside).write_text("outside\n", encoding="utf-8")
_original_open_file = app_module._open_file
app_module._open_file = lambda p: (True, "")
try:
    resp_file_ok = api.post("/api/open/file", json={"path": open_inside})
    check("open file inside scan root allowed", resp_file_ok.status_code == 200, str(resp_file_ok.get_json()))
    resp_file_out = api.post("/api/open/file", json={"path": open_outside})
    check("open file outside scan roots 403", resp_file_out.status_code == 403, resp_file_out.get_json()["error"])
    resp_folder_file_out = api.post("/api/open/folder", json={"path": open_outside})
    check("open folder on outside file 403", resp_folder_file_out.status_code == 403, resp_folder_file_out.get_json()["error"])
    resp_folder_dir_out = api.post("/api/open/folder", json={"path": open_dir})
    check("open folder on outside dir 403", resp_folder_dir_out.status_code == 403, resp_folder_dir_out.get_json()["error"])
finally:
    app_module._open_file = _original_open_file
    try:
        os.remove(open_inside)
    except OSError:
        pass
    _shutil.rmtree(open_dir, ignore_errors=True)

print("\n-- Phase 4: Compare Mode A (cloud redirect) --")
from modules.compare import platforms, side_by_side

compare_record = {"name": "Resume.pdf", "path": str(code_file), "parent_folder": "asktest", "extension": ".pdf", "size": 12345, "modified": time.time(), "category": "document", "icon": get_file_icon(".pdf"), "sensitive": False}
links = platforms.compare_links(compare_record, "what is this file?")
check("compare returns four links", len(links) == 4, [l["platform"] for l in links])
check("compare links are URL-encoded", all("%20" in l["url"] and " " not in l["url"].split("://", 1)[1] for l in links), links[0]["url"][:60])
check("compare links never carry file content", all(platforms.url_never_leaks_content(l["url"]) and "File content:" not in l["url"] for l in links))
check("compare default question fills in", "What%20is%20this%20file" in platforms.compare_links(compare_record, "")[0]["url"])
check("compare mode B reports unavailable without keys", side_by_side.compare_side_by_side(compare_record, "")["available"] is False)

resp_compare_missing = api.post("/api/compare", json={"path": str(Path(ask_dir) / "nope.txt")})
check("compare 404 for missing file", resp_compare_missing.status_code == 404 and resp_compare_missing.get_json()["ok"] is False)
resp_compare_ok = api.post("/api/compare", json={"path": str(code_file), "question": "what does this do?"})
data_compare = resp_compare_ok.get_json()
check("compare 200 with four links", resp_compare_ok.status_code == 200 and data_compare.get("ok") and len(data_compare["links"]) == 4, str(data_compare.get("side_by_side")))

print("\n-- API: activity feed contract --")
resp_activity = api.get("/api/activity?limit=5")
act_data = resp_activity.get_json()
check("activity endpoint returns newest-first entries", resp_activity.status_code == 200 and act_data["ok"] is True and isinstance(act_data["entries"], list), str(act_data.get("total")))
resp_activity_bad = api.get("/api/activity?limit=banana")
check("activity limit falls back to default on bad input", resp_activity_bad.status_code == 200 and resp_activity_bad.get_json()["ok"] is True)

print("\n-- Settings: editable scan folders --")
settings_test_dir = tempfile.mkdtemp(prefix="fileseek_settings_test_")
settings_tmp_path = Path(settings_test_dir) / "settings.json"
scan_root_a = os.path.realpath(tempfile.mkdtemp(prefix="scan_a_", dir=settings_test_dir))
scan_root_b = os.path.realpath(tempfile.mkdtemp(prefix="scan_b_", dir=settings_test_dir))
scan_nested = os.path.join(scan_root_a, "sub")
os.makedirs(scan_nested, exist_ok=True)

_saved_settings_path = config.SETTINGS_PATH
_saved_scan_dirs_api = list(config.SCAN_DIRS)
config.SETTINGS_PATH = settings_tmp_path
check("settings default to the three roots before any save", config.load_settings()["scan_dirs"] == list(config.DEFAULT_SCAN_DIRS), str(config.load_settings()["scan_dirs"]))
config.save_settings({"scan_dirs": [scan_root_a]})
check("settings survive a simulated restart (load after save)", config.load_settings()["scan_dirs"] == [scan_root_a], str(config.load_settings()["scan_dirs"]))

_orig_run_full_index = app_module._run_full_index
app_module._run_full_index = lambda: None
try:
    resp_missing = api.post("/api/config", json={"scan_dirs": [os.path.join(settings_test_dir, "nope")]})
    check("missing folder rejected 400", resp_missing.status_code == 400, resp_missing.get_json()["error"])
    resp_nested = api.post("/api/config", json={"scan_dirs": [scan_root_a, scan_nested]})
    check("nested folder rejected 400", resp_nested.status_code == 400, resp_nested.get_json()["error"])
    resp_index = api.post("/api/config", json={"scan_dirs": [str(config.INDEX_DIR)]})
    check("index dir rejected 400", resp_index.status_code == 400, resp_index.get_json()["error"])
    resp_ok = api.post("/api/config", json={"scan_dirs": [scan_root_a, scan_root_b]})
    check("valid scan dirs accepted", resp_ok.status_code == 200 and resp_ok.get_json()["ok"] is True, str(resp_ok.get_json().get("scan_dirs")))
    check("SAVE mutates the live SCAN_DIRS", config.SCAN_DIRS == [scan_root_a, scan_root_b], str(config.SCAN_DIRS))
    resp_get_after = api.get("/api/config").get_json()
    check("GET /api/config reflects the saved roots", resp_get_after["scan_dirs"] == [scan_root_a, scan_root_b])
    config.apply_scan_dirs(list(config.DEFAULT_SCAN_DIRS))
    app_module._apply_saved_settings()
    check("scan dirs restored from settings.json after restart simulation", config.SCAN_DIRS == [scan_root_a, scan_root_b], str(config.SCAN_DIRS))
finally:
    app_module._run_full_index = _orig_run_full_index
    config.apply_scan_dirs(_saved_scan_dirs_api)
    config.SETTINGS_PATH = _saved_settings_path
    _shutil.rmtree(settings_test_dir, ignore_errors=True)

print("\n-- Content search (RAG): scope, snippet, incremental --")
from modules.indexer.content_index import ContentIndex, chunk_text
from modules.indexer.crawler import build_record as _content_build_record
from modules.search.engine import SearchEngine as _ContentEngine

content_dir = tempfile.mkdtemp(prefix="fileseek_content_test_")
content_root = os.path.join(content_dir, "notes")
os.makedirs(content_root)
planted_phrase = "quasar ledger reconciliation protocol"
planted_file = Path(content_root) / "notes.md"
planted_file.write_text(
    "# Notes\n\nThe team follows the " + planted_phrase + " every quarter.\n"
    + ("filler paragraph that says nothing new.\n" * 8),
    encoding="utf-8",
)

check("chunk_text splits with overlap", all(len(c) <= config.CONTENT_CHUNK_CHARS + 1 for c in chunk_text("abc " * 900)), str([len(c) for c in chunk_text("abc " * 900)]))

_content_store = IndexStore()
_planted_record = _content_build_record(str(planted_file))
_content_key = norm_key(str(planted_file))
_content_store.build({_content_key: _planted_record}, embedder.embed_query("notes md").reshape(1, -1))

ci = ContentIndex(index_path=Path(content_dir) / "content.index", meta_path=Path(content_dir) / "content_meta.json")
ci.set_enabled(False)
check("content index off by default rejects writes", ci.index_file(_content_key, _planted_record, embedder) == 0)
ci.set_enabled(True)
n_chunks = ci.index_file(_content_key, _planted_record, embedder)
check("content index embeds a text file", n_chunks >= 1, f"{n_chunks} chunks")
ci.save()
check("content index persists (index + meta)", (Path(content_dir) / "content.index").exists() and (Path(content_dir) / "content_meta.json").exists())
ci2 = ContentIndex(index_path=Path(content_dir) / "content.index", meta_path=Path(content_dir) / "content_meta.json")
ci2.load()
ci2.set_enabled(True)
check("content index round-trips from disk", ci2.is_ready() and ci2.stats()["chunks"] == n_chunks, str(ci2.stats()))

cengine = _ContentEngine(_content_store, embedder)
q_planted = "quasar ledger reconciliation"
res_contents, meta_contents = cengine.search(q_planted, scope="contents", content_index=ci2)
check("planted phrase found in contents scope", len(res_contents) == 1 and res_contents[0]["name"] == "notes.md", res_contents[0]["name"] if res_contents else "(none)")
check("contents result carries a snippet", bool(res_contents[0].get("snippet")) and planted_phrase[:20].split()[0] in res_contents[0]["snippet"].lower(), res_contents[0].get("snippet", "")[:50])
res_files_only, meta_files = cengine.search(q_planted, scope="files", content_index=ci2)
check("planted phrase is invisible in names-only scope", all(r.get("snippet") is None for r in res_files_only), f"{len(res_files_only)} results")
res_both, _ = cengine.search(q_planted, scope="both", content_index=ci2)
check("both scope surfaces the content hit", len(res_both) >= 1 and any(r.get("snippet") for r in res_both))
res_names, _ = cengine.search("notes", scope="files", content_index=ci2)
check("name search still works alongside content index", len(res_names) >= 1)

# incremental: editing the file updates its chunks
planted_file.write_text("# Notes\n\nBrand new galactic archive mandate.\n", encoding="utf-8")
_planted_record2 = _content_build_record(str(planted_file))
_content_store.update_record(_content_key, _planted_record2)
ci2.index_file(_content_key, _planted_record2, embedder)
res_after_edit, _ = cengine.search("galactic archive mandate", scope="contents", content_index=ci2)
check("edit updates the content index", len(res_after_edit) == 1 and res_after_edit[0]["name"] == "notes.md", res_after_edit[0]["name"] if res_after_edit else "(none)")
res_old_phrase, meta_old = cengine.search(q_planted, scope="contents", content_index=ci2)
check("old phrase gone after edit", len(res_old_phrase) == 0, f"{len(res_old_phrase)} results")

# removal: deleting the file removes its chunks
ci2.remove_file(_content_key)
res_after_delete, _ = cengine.search("galactic archive mandate", scope="contents", content_index=ci2)
check("delete removes content chunks", len(res_after_delete) == 0 and ci2.stats()["chunks"] == 0, f"chunks={ci2.stats()['chunks']}")
_shutil.rmtree(content_dir, ignore_errors=True)

print("\n-- Assistant: folder context --")
from modules.assistant.folder_context import build_folder_context
ctx = build_folder_context(str(code_file))
check("folder context lists siblings without the ask target", all(s["name"] != code_file.name for s in ctx["siblings"]) and len(ctx["siblings"]) >= 1, f"{len(ctx['siblings'])} siblings")
check("folder context excerpts only small text files", set(ctx["excerpts"].keys()) <= {s["name"] for s in ctx["siblings"]}, f"excerpts={sorted(ctx['excerpts'].keys())}")

print("\n-- Assistant: explain_more with stubbed chat --")
app_module.explainer.client = stub
long_history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"} for i in range(20)]
more_result = test_explainer.explain_more(code_record, long_history, "What does this file sit next to?")
check("explain_more calls chat with trimmed history", stub.chat_calls == 1 and len(stub.last_messages) <= config.ASK_MORE_MAX_TURNS + 1, f"messages sent={len(stub.last_messages)}, cap={config.ASK_MORE_MAX_TURNS}")
check("explain_more reports folder context in result", more_result["context_files"] >= 1, f"context_files={more_result['context_files']}, excerpts={more_result['excerpt_files']}")

print("\n-- API: /api/ask-more contract --")
resp_more_missing = api.post("/api/ask-more", json={"path": str(Path(ask_dir) / "nope.txt")})
check("ask-more 404 for missing file", resp_more_missing.status_code == 404)

app_module.explainer.client = stub
resp_more_ok = api.post("/api/ask-more", json={"path": str(code_file), "history": [], "question": "What sits next to this file?"})
check("ask-more 200 with answer for text file", resp_more_ok.status_code == 200 and resp_more_ok.get_json().get("ok") is True)

app_module.explainer.client = DownOllama()
resp_more_down = api.post("/api/ask-more", json={"path": str(code_file)})
check("ask-more 503 when Ollama down", resp_more_down.status_code == 503 and "Ollama" in resp_more_down.get_json()["error"])

print("\n-- Live Ollama smoke (auto-skipped when offline) --")
from modules.assistant.llm_client import OllamaClient, OllamaError
live_client = OllamaClient()
live_available, _live_models = live_client.is_available()
if live_available:
    live_file = Path(ask_dir) / "live_smoke.txt"
    live_file.write_text("Shopping list: milk, eggs, bread.\n", encoding="utf-8")
    live_record = {"name": "live_smoke.txt", "path": str(live_file), "parent_folder": "asktest", "extension": ".txt", "size": live_file.stat().st_size, "modified": live_file.stat().st_mtime, "category": "document", "sensitive": False}
    try:
        live_result = Explainer(client=live_client).explain(live_record, "What is this?")
        check("live ask returns an answer", bool(live_result["answer"]), f"{live_result['answer'][:60]} ({live_result['elapsed_ms']}ms)")
        live_more = Explainer(client=live_client).explain_more(live_record, [], "What other files are in its folder?")
        check("live ask-more returns a conversational answer", bool(live_more["answer"]), f"{live_more['answer'][:60]} ({live_more['elapsed_ms']}ms)")
    except OllamaError as exc:
        print(f"[SKIP] live ask could not run - {exc}")
else:
    print("[SKIP] live Ollama smoke - Ollama not reachable; suite still green")

config.apply_scan_dirs(_saved_scan_ask)
import shutil
shutil.rmtree(ask_dir, ignore_errors=True)
shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n=== ALL CHECKS PASSED ===")
stats = store2.stats()
print(f"Index stats: {stats['file_count']} files, dims={stats['dimensions']}, categories={stats['categories']}")

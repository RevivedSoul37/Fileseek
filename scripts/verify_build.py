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

resp_missing = api.post("/api/ask", json={"path": str(Path(ask_dir) / "nope.txt")})
check("ask 404 for missing file", resp_missing.status_code == 404 and resp_missing.get_json()["ok"] is False)

app_module.explainer.client = stub
resp_ok = api.post("/api/ask", json={"path": str(code_file)})
check("ask 200 with answer for text file", resp_ok.status_code == 200 and resp_ok.get_json().get("ok") is True, str(resp_ok.get_json()).strip(". ")[:80])

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

import shutil
shutil.rmtree(ask_dir, ignore_errors=True)
shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n=== ALL CHECKS PASSED ===")
stats = store2.stats()
print(f"Index stats: {stats['file_count']} files, dims={stats['dimensions']}, categories={stats['categories']}")

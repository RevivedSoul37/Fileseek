import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.core import config
from modules.core.utils import format_size, time_ago
from modules.indexer.crawler import build_record, walk_files
from modules.indexer.embedder import Embedder
from modules.indexer.index_store import IndexStore
from modules.search.engine import SearchEngine
from modules.watcher.monitor import WatcherService
from modules.watcher.snapshot_store import norm_key
from modules.assistant.explainer import Explainer
from modules.assistant.llm_client import OllamaError
from modules.assistant.prompts import DEFAULT_QUESTION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fileseek")
for noisy in ("httpx", "httpcore", "huggingface_hub", "sentence_transformers", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

app = Flask(__name__)

store = IndexStore()
embedder = Embedder(config.EMBED_MODEL_NAME)
engine = SearchEngine(store, embedder)

watcher = WatcherService(store, embedder)

explainer = Explainer()

index_state = {"running": False, "progress": "", "files": 0}
index_lock = threading.Lock()


def _open_in_explorer(path):
    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])


def _open_file(path):
    try:
        os.startfile(path)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def _is_within_scan_roots(path):
    """True if `path` sits inside one of the configured scan roots, or is
    already tracked in the index. Flask binds 127.0.0.1 only; this check makes
    the open endpoints safe by construction rather than by luck."""
    try:
        resolved = os.path.realpath(path)
    except OSError:
        return False
    for root in config.SCAN_DIRS:
        root_resolved = os.path.realpath(root)
        if resolved == root_resolved or resolved.startswith(root_resolved + os.sep):
            return True
    if store.is_ready() and store.get_record(norm_key(path)) is not None:
        return True
    return False


_shutdown_done = threading.Event()


def _graceful_shutdown(*args):
    """Stop the watcher and save all state so nothing queued up in the last
    30 s is lost. Safe to call multiple times (atexit + signal)."""
    if _shutdown_done.is_set():
        return
    _shutdown_done.set()
    if watcher.running:
        log.info("Shutting down: stopping watcher and saving state...")
        watcher.stop()
    else:
        try:
            store.save()
            watcher.snapshots.save()
        except Exception:
            log.exception("Shutdown save failed")


def _install_signal_handlers():
    signal.signal(signal.SIGINT, _sigint_handler)
    if hasattr(signal, "SIGBREAK"):  # Windows console Ctrl+Break / close button
        signal.signal(signal.SIGBREAK, _sigint_handler)
    atexit.register(_graceful_shutdown)


def _sigint_handler(signum, frame):
    _graceful_shutdown()
    os._exit(0 if signum == signal.SIGINT else 1)


def _run_full_index():
    with index_lock:
        if index_state["running"]:
            return
        index_state["running"] = True
    started = time.perf_counter()
    try:
        log.info("Index run started - scanning %d folders", len(config.SCAN_DIRS))
        index_state["progress"] = "Scanning folders..."
        scan_started = time.perf_counter()
        records = walk_files(config.SCAN_DIRS)
        total = len(records)
        index_state["files"] = total
        log.info("Scan complete: %d files in %.1fs", total, time.perf_counter() - scan_started)
        log.info("Embedding model: %s", config.EMBED_MODEL_NAME)
        index_state["progress"] = f"Scanned {total} files. Loading AI model..."
        texts = [embedder.build_text(r) for r in records.values()]
        chunks = []
        step = 1000
        for i in range(0, total, step):
            chunk = texts[i:i + step]
            chunks.append(embedder.embed_texts(
                chunk, batch_size=config.EMBED_BATCH_SIZE, show_progress=False
            ))
            done = min(i + step, total)
            log.info("Embedding %d/%d (%.0f%%)", done, total, done * 100.0 / max(total, 1))
            index_state["progress"] = f"Embedding {done}/{total}..."
        embeddings = np.concatenate(chunks) if chunks else np.zeros((0, 384), dtype="float32")
        log.info("Building FAISS index over %d vectors...", total)
        index_state["progress"] = "Building FAISS index..."
        store.build(records, embeddings)
        store.save()
        log.info("Index saved: %d vectors -> %s", store.index.ntotal, config.INDEX_PATH)
        index_state["progress"] = f"Indexed {total} files at {time.strftime('%H:%M:%S')}"
        log.info("Index run complete: %d files in %.1fs", total, time.perf_counter() - started)
        _start_watcher_if_ready()
    except Exception as exc:
        log.exception("Index run failed: %s", exc)
        index_state["progress"] = f"Index failed: {exc}"
    finally:
        index_state["running"] = False


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat")
def chat_page():
    return render_template("chat.html")


@app.route("/api/file-card", methods=["GET"])
def api_file_card():
    from modules.search.ranker import record_to_result
    path = request.args.get("path", "")
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "File not found - it may have been moved or deleted"}), 404
    record = store.get_record(norm_key(path)) if store.is_ready() else None
    if record is None:
        record = build_record(path)
    if record is None:
        return jsonify({"ok": False, "error": "Could not read this file"}), 404
    result = record_to_result(record)
    result["ok"] = True
    return jsonify(result)


@app.route("/api/search", methods=["POST"])
def api_search():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query", "")
    category = payload.get("category", "all")
    limit = min(int(payload.get("limit") or config.MAX_RESULTS), 1000)
    if not store.is_ready():
        return jsonify({"results": [], "indexed": False, "query": query,
                        "total": 0, "category_counts": {}})
    results, counts = engine.search(query, max_results=limit, category=category)
    return jsonify({"results": results, "indexed": True, "query": query,
                    "total": counts["total"], "category_counts": counts["categories"]})


@app.route("/api/browse", methods=["GET"])
def api_browse():
    from modules.search.ranker import record_to_result
    category = request.args.get("category", "all")
    limit = min(int(request.args.get("limit", 60)), 500)
    if not store.is_ready():
        return jsonify({"results": [], "indexed": False, "total": 0})
    records = list(store.metadata.values())
    if category and category != "all":
        records = [r for r in records if r.get("category") == category]
    records.sort(key=lambda r: r.get("modified") or 0, reverse=True)
    total = len(records)
    page = records[:limit]
    results = [record_to_result(r) for r in page]
    return jsonify({"results": results, "indexed": True, "total": total})


@app.route("/api/index", methods=["POST"])
def api_index():
    with index_lock:
        if index_state["running"]:
            return jsonify({"started": False, "reason": "already running"})
    log.info("Re-index requested via API")
    thread = threading.Thread(target=_run_full_index, daemon=True)
    thread.start()
    return jsonify({"started": True})


@app.route("/api/status", methods=["GET"])
def api_status():
    stats = store.stats()
    ask_available = explainer.client.is_available()[0]
    return jsonify({
        "indexed": store.is_ready(),
        "file_count": stats["file_count"],
        "last_indexed": stats["last_indexed"],
        "built_at": stats["built_at"],
        "categories": stats["categories"],
        "indexing": index_state["running"],
        "progress": index_state["progress"],
        "watching": watcher.running,
        "snapshot_count": len(watcher.snapshots.snapshots),
        "ask_available": ask_available,
    })


@app.route("/api/ask", methods=["POST"])
def api_ask():
    payload = request.get_json(silent=True) or {}
    path = payload.get("path", "")
    question = payload.get("question", "")
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "File not found - it may have been moved or deleted"}), 404
    record = store.get_record(norm_key(path)) if store.is_ready() else None
    if record is None:
        record = build_record(path)
    if record is None:
        return jsonify({"ok": False, "error": "Could not read this file"}), 404
    available, _ = explainer.client.is_available()
    if not available:
        return jsonify({
            "ok": False,
            "error": "Ollama is not running - start it with `ollama serve`, then try again",
        }), 503
    try:
        result = explainer.explain(record, question)
    except OllamaError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    result["ok"] = True
    result["question"] = question.strip() or DEFAULT_QUESTION
    result["sensitive"] = bool(record.get("sensitive"))
    return jsonify(result)


@app.route("/api/ask-more", methods=["POST"])
def api_ask_more():
    payload = request.get_json(silent=True) or {}
    path = payload.get("path", "")
    question = payload.get("question", "")
    history = payload.get("history") or []
    if not isinstance(history, list):
        history = []
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "File not found - it may have been moved or deleted"}), 404
    record = store.get_record(norm_key(path)) if store.is_ready() else None
    if record is None:
        record = build_record(path)
    if record is None:
        return jsonify({"ok": False, "error": "Could not read this file"}), 404
    available, _ = explainer.client.is_available()
    if not available:
        return jsonify({
            "ok": False,
            "error": "Ollama is not running - start it with `ollama serve`, then try again",
        }), 503
    try:
        result = explainer.explain_more(record, history, question)
    except OllamaError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    result["ok"] = True
    result["sensitive"] = bool(record.get("sensitive"))
    return jsonify(result)


@app.route("/api/open/file", methods=["POST"])
def api_open_file():
    payload = request.get_json(silent=True) or {}
    path = payload.get("path", "")
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "File not found"}), 404
    if not _is_within_scan_roots(path):
        return jsonify({"ok": False, "error": "Refused - path is outside the scan roots"}), 403
    ok, err = _open_file(path)
    return jsonify({"ok": ok, "error": err}), (200 if ok else 500)


@app.route("/api/open/folder", methods=["POST"])
def api_open_folder():
    payload = request.get_json(silent=True) or {}
    path = payload.get("path", "")
    if not path:
        return jsonify({"ok": False, "error": "No path given"}), 400
    if os.path.isfile(path):
        if not _is_within_scan_roots(path):
            return jsonify({"ok": False, "error": "Refused - path is outside the scan roots"}), 403
        _open_in_explorer(path)
    elif os.path.isdir(path):
        if not _is_within_scan_roots(path):
            return jsonify({"ok": False, "error": "Refused - path is outside the scan roots"}), 403
        subprocess.Popen(["explorer", os.path.normpath(path)])
    else:
        return jsonify({"ok": False, "error": "Path not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/config", methods=["GET"])
def api_config():
    return jsonify({
        "scan_dirs": config.SCAN_DIRS,
        "exclude_dirs": sorted(config.EXCLUDE_DIR_NAMES),
        "port": config.PORT,
        "max_results": config.MAX_RESULTS,
        "embed_model": config.EMBED_MODEL_NAME,
        "sensitive_markers": list(config.SENSITIVE_NAME_MARKERS),
    })


def _start_watcher_if_ready():
    if watcher.running or not store.is_ready():
        return
    watcher.seed_snapshots()
    if watcher.start():
        index_state["progress"] = f"Watcher live ({len(watcher.snapshots.snapshots)} snapshots)"
    else:
        log.warning("Watcher failed to start")


def _auto_load_or_build():
    loaded = store.load()
    if loaded:
        log.info("Loaded existing index: %d files from %s", len(store.metadata), config.INDEX_PATH)
        index_state["progress"] = f"Loaded existing index ({len(store.metadata)} files)"
        _start_watcher_if_ready()
        return
    log.info("No saved index found - building first index")
    thread = threading.Thread(target=_run_full_index, daemon=True)
    thread.start()


def _port_busy():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((config.HOST, config.PORT)) == 0


if __name__ == "__main__":
    if _port_busy():
        log.error(
            "Port %d is already in use - another FileSeek (or any app) is running. "
            "Close that console window first, then relaunch.",
            config.PORT,
        )
        input("Press Enter to close this window...")
        raise SystemExit(1)
    log.info("FileSeek starting on http://%s:%d", config.HOST, config.PORT)
    _install_signal_handlers()
    _auto_load_or_build()
    app.run(host=config.HOST, port=config.PORT, debug=False)

import json
import time
from pathlib import Path

USER_HOME = Path.home()

DEFAULT_SCAN_DIRS = [
    str(USER_HOME / "Downloads"),
    str(USER_HOME / "Documents"),
    str(USER_HOME / "Desktop"),
]

# Mutated in place (apply_scan_dirs) so every module that imported this list
# sees the live value after a settings change.
SCAN_DIRS = list(DEFAULT_SCAN_DIRS)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# No blanket path exclusions: junk dirs (venv, __pycache__, node_modules...)
# are already excluded by name below. The app's own folder now gets indexed
# so its planning docs are searchable.
EXCLUDE_PATHS = []

EXCLUDE_DIR_NAMES = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    ".idea", ".vscode", ".next", ".cache", ".pytest_cache",
    "dist", "build", "appdata", "$recycle.bin",
    "system volume information", ".kilo",
}

SENSITIVE_NAME_MARKERS = (
    "api_key", "apikey", "api-key", "secret", "credential",
    "password", "passwd", "token", "backup code", "backup-code",
    "private key", "private_key", ".pem", ".key", "2fa", "otp",
)

INDEX_DIR = PROJECT_ROOT / "data"
INDEX_PATH = INDEX_DIR / "fileseek.index"
METADATA_PATH = INDEX_DIR / "metadata.json"
SNAPSHOT_PATH = INDEX_DIR / "snapshots.json"  # legacy whole-file store (retired on upgrade)
SNAPSHOT_DB_PATH = INDEX_DIR / "snapshots.db"
ACTIVITY_PATH = INDEX_DIR / "activity.json"
SETTINGS_PATH = INDEX_DIR / "settings.json"
CONTENT_INDEX_PATH = INDEX_DIR / "content.index"
CONTENT_META_PATH = INDEX_DIR / "content_meta.json"

ACTIVITY_MAX_ENTRIES = 200
ACTIVITY_DEFAULT_LIMIT = 50

CONTENT_MAX_FILE_BYTES = 256 * 1024
CONTENT_CHUNK_CHARS = 500
CONTENT_CHUNK_STRIDE = 400
CONTENT_MAX_CHUNKS_PER_FILE = 128
CONTENT_MATCH_FLOOR = 0.35
CONTENT_SNIPPET_CHARS = 140

DIFF_MAX_BYTES = 64 * 1024
DIFF_MAX_LINES = 20_000
SNAPSHOT_MAX_HASH_BYTES = 64 * 1024 * 1024

WATCH_DEBOUNCE_SECONDS = 2.0
WATCH_MAX_BATCH_SECONDS = 10.0
WATCH_SAVE_INTERVAL_SECONDS = 30.0

HOST = "127.0.0.1"
PORT = 7860
MAX_RESULTS = 20
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_BATCH_SIZE = 64
SEARCH_DEBOUNCE_MS = 300
SEARCH_MATCH_FLOOR = 0.25
SEARCH_COUNT_POOL = 1000

OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3:8b"
OLLAMA_CODE_MODEL = "qwen2.5-coder"
ASK_MAX_CHARS = 8000
ASK_TIMEOUT_SECONDS = 60

ASK_MORE_MAX_SIBLINGS = 25
ASK_MORE_EXCERPT_FILES = 3
ASK_MORE_EXCERPT_CHARS = 1500
ASK_MORE_MAX_TURNS = 6


def load_settings():
    """Read data/settings.json; missing/corrupt returns defaults. Keeps the
    shape {"scan_dirs": [...]}; unknown keys are preserved opaquely."""
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"scan_dirs": list(DEFAULT_SCAN_DIRS)}
        scan_dirs = payload.get("scan_dirs")
        if not isinstance(scan_dirs, list) or not scan_dirs:
            payload["scan_dirs"] = list(DEFAULT_SCAN_DIRS)
        payload.setdefault("scan_dirs", list(DEFAULT_SCAN_DIRS))
        return payload
    except (OSError, ValueError):
        return {"scan_dirs": list(DEFAULT_SCAN_DIRS)}


def save_settings(settings):
    """Persist to data/settings.json with atomic tmp-replace. Returns True."""
    payload = dict(settings or {})
    payload.setdefault("scan_dirs", list(SCAN_DIRS))
    payload["saved_at"] = time.time()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_name(SETTINGS_PATH.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(SETTINGS_PATH)
    return True


def apply_scan_dirs(dirs):
    """Replace SCAN_DIRS in place (see module docstring) with the given list."""
    SCAN_DIRS[:] = [str(d) for d in dirs]
    return list(SCAN_DIRS)


from pathlib import Path

USER_HOME = Path.home()

SCAN_DIRS = [
    str(USER_HOME / "Downloads"),
    str(USER_HOME / "Documents"),
    str(USER_HOME / "Desktop"),
]

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

HOST = "127.0.0.1"
PORT = 7860
MAX_RESULTS = 20
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_BATCH_SIZE = 64
SEARCH_DEBOUNCE_MS = 300

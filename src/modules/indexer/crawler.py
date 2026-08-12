import os
from pathlib import Path

from ..core.config import SCAN_DIRS, EXCLUDE_PATHS, EXCLUDE_DIR_NAMES, SENSITIVE_NAME_MARKERS
from ..core.utils import get_file_category, get_file_icon


def _is_excluded_dir(dir_path):
    resolved = str(Path(dir_path).resolve()).lower()
    if any(resolved.startswith(p.lower()) for p in EXCLUDE_PATHS):
        return True
    try:
        parts = Path(dir_path).parts
    except OSError:
        parts = ()
    for part in parts:
        if part.lower() in EXCLUDE_DIR_NAMES:
            return True
    return False


def _marks_sensitive(name):
    lowered = name.lower()
    return any(marker in lowered for marker in SENSITIVE_NAME_MARKERS)


def build_record(full_path):
    try:
        stat = os.stat(full_path)
        size = stat.st_size
        modified = stat.st_mtime
    except (OSError, PermissionError):
        return None
    filename = os.path.basename(full_path)
    extension = os.path.splitext(filename)[1].lower()
    return {
        "name": filename,
        "path": full_path,
        "parent_folder": Path(os.path.dirname(full_path)).name,
        "extension": extension,
        "size": size,
        "modified": modified,
        "category": get_file_category(extension),
        "icon": get_file_icon(extension),
        "sensitive": _marks_sensitive(filename),
    }


def walk_files(root_dirs=None):
    found = {}
    roots = root_dirs or SCAN_DIRS
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
            dirnames[:] = [d for d in dirnames if not _is_excluded_dir(os.path.join(dirpath, d))]
            if _is_excluded_dir(dirpath):
                dirnames[:] = []
                continue
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                record = build_record(full_path)
                if record is None:
                    continue
                found[full_path.lower()] = record
    return found

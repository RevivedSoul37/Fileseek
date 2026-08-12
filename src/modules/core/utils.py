import time
from datetime import datetime

CATEGORY_BY_EXT = {
    ".pdf": "document", ".doc": "document", ".docx": "document",
    ".txt": "document", ".md": "document", ".rtf": "document",
    ".odt": "document", ".epub": "document", ".log": "document",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
    ".avif": "image", ".svg": "image", ".gif": "image", ".bmp": "image",
    ".ico": "image", ".heic": "image", ".tif": "image",
    ".mp4": "media", ".mkv": "media", ".avi": "media", ".mov": "media",
    ".webm": "media", ".mp3": "media", ".wav": "media", ".flac": "media",
    ".m4a": "media", ".ogg": "media", ".aac": "media", ".opus": "media",
    ".py": "code", ".js": "code", ".jsx": "code", ".ts": "code",
    ".tsx": "code", ".html": "code", ".css": "code", ".java": "code",
    ".cpp": "code", ".c": "code", ".h": "code", ".rs": "code",
    ".go": "code", ".php": "code", ".rb": "code", ".sh": "code",
    ".ps1": "code", ".bat": "code", ".sql": "code", ".ipynb": "code",
    ".lua": "code", ".swift": "code", ".kt": "code",
    ".zip": "archive", ".rar": "archive", ".7z": "archive",
    ".tar": "archive", ".gz": "archive", ".bz2": "archive",
    ".iso": "archive", ".torrent": "archive",
    ".csv": "data", ".xlsx": "data", ".xls": "data", ".parquet": "data",
    ".sqlite": "data", ".db": "data", ".json": "data", ".xml": "data",
    ".yaml": "data", ".yml": "data",
}

ICON_BY_CATEGORY = {
    "document": "\U0001F4C4",
    "image": "\U0001F5BC\uFE0F",
    "media": "\U0001F3AC",
    "code": "\U0001F4BB",
    "archive": "\U0001F4E6",
    "data": "\U0001F4CA",
    "other": "\U0001F4C1",
}

EXT_WORDS = {
    ".pdf": "pdf document portable document format report manual",
    ".docx": "word document text report",
    ".doc": "word document text report",
    ".txt": "plain text note",
    ".md": "markdown readme note documentation",
    ".png": "png picture image photo screenshot",
    ".jpg": "jpeg photo picture image",
    ".jpeg": "jpeg photo picture image",
    ".webp": "web picture image",
    ".svg": "svg vector graphic logo icon",
    ".gif": "animated gif image",
    ".mp4": "mp4 video movie clip recording",
    ".mkv": "video movie",
    ".mov": "video movie clip",
    ".mp3": "mp3 audio music song sound",
    ".wav": "wav audio sound recording",
    ".flac": "lossless audio music",
    ".m4a": "audio music recording",
    ".py": "python script code program",
    ".js": "javascript code program",
    ".ts": "typescript code program",
    ".html": "html webpage website",
    ".css": "css stylesheet design",
    ".ipynb": "jupyter notebook data analysis",
    ".zip": "zip archive compressed folder",
    ".7z": "7z archive compressed folder",
    ".rar": "rar archive compressed folder",
    ".exe": "installer setup program application",
    ".msi": "installer setup program application",
    ".csv": "csv spreadsheet dataset table rows columns",
    ".xlsx": "excel spreadsheet dataset workbook",
    ".json": "json data config settings",
    ".bat": "batch script launcher windows command",
    ".torrent": "torrent download bittorrent",
    ".epub": "ebook book reading",
}


def get_file_category(extension):
    return CATEGORY_BY_EXT.get((extension or "").lower(), "other")


def get_file_icon(extension):
    return ICON_BY_CATEGORY[get_file_category(extension)]


def format_size(size_bytes):
    if not size_bytes or size_bytes < 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024


def time_ago(timestamp):
    if not timestamp:
        return "unknown"
    delta = max(0, int(time.time() - timestamp))
    if delta < 60:
        return "just now"
    if delta < 3600:
        minutes = delta // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if delta < 86400:
        hours = delta // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = delta // 86400
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    modified = datetime.fromtimestamp(timestamp)
    if modified.year == datetime.now().year:
        return modified.strftime("%b %d")
    return modified.strftime("%b %d, %Y")

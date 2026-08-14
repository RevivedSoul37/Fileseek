import time

from modules.core.utils import (
    decode_excerpt,
    format_size,
    get_file_category,
    get_file_icon,
    time_ago,
)


def test_format_size():
    assert format_size(1048576) == "1.0 MB"
    assert format_size(0) == "0 B"


def test_categories():
    assert get_file_category(".pdf") == "document"
    assert get_file_category(".mp4") == "media"
    assert get_file_category(".py") == "code"


def test_icons_not_empty():
    assert get_file_icon(".jpg") != ""


def test_time_ago():
    assert isinstance(time_ago(time.time() - 3600), str)


def test_decode_excerpt_text_and_binary():
    assert decode_excerpt("héllo world".encode("utf-8")) == "héllo world"
    assert decode_excerpt(b"\x89PNG\r\n\x1a\n\x00\x00") is None

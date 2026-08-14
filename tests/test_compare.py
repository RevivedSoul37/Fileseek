from modules.compare import platforms, side_by_side

RECORD = {
    "name": "Résumé.pdf",
    "parent_folder": "Jobs",
    "extension": ".pdf",
    "category": "document",
    "size": 12345,
    "sensitive": True,
}


def test_compare_returns_four_platforms():
    links = platforms.compare_links(RECORD, "what is this file?")
    assert [l["platform"] for l in links] == ["ChatGPT", "Gemini", "Claude", "Perplexity"]


def test_compare_urls_are_encoded_no_raw_spaces():
    for link in platforms.compare_links(RECORD, "question with spaces"):
        host_and_query = link["url"].split("://", 1)[1]
        assert " " not in host_and_query
        assert "%20" in link["url"]


def test_compare_never_leaks_file_content():
    for link in platforms.compare_links(RECORD, "summarize"):
        assert "File content:" not in link["url"]
        assert platforms.url_never_leaks_content(link["url"])


def test_default_question_applies_on_empty():
    links = platforms.compare_links(RECORD, "   ")
    assert "What%20is%20this%20file" in links[0]["url"]


def test_mode_b_off_without_keys(monkeypatch):
    for var in ("FILESEEK_CHATGPT_KEY", "FILESEEK_GEMINI_KEY", "FILESEEK_CLAUDE_KEY"):
        monkeypatch.delenv(var, raising=False)
    result = side_by_side.compare_side_by_side(RECORD, "q")
    assert result["available"] is False
    assert result["answers"] == []

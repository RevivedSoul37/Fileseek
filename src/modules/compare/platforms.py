"""Free redirect builders for Phase 4, Mode A: open a cloud AI in the browser
and paste the question there. Payload = file name/type/size + question only,
NEVER file content. Nothing leaves this machine until the user clicks."""

import urllib.parse


def _payload_record(record, question):
    """The shared fact card: metadata the cloud AI gets to see."""
    return {
        "name": record.get("name", "unknown"),
        "folder": record.get("parent_folder", "unknown"),
        "extension": record.get("extension") or "no extension",
        "category": record.get("category", "other"),
        "size": record.get("size", 0),
        "sensitive": bool(record.get("sensitive")),
        "question": question,
    }


def _preface(payload):
    """The prompt text sent as URL parameters. Plain language, same for every
    platform, so the user knows exactly what context the AI can see."""
    return (
        "I am browsing my local file catalog on my computer (FileSeek). "
        "Here is what it knows about one file:\n"
        f"- Name: {payload['name']}\n"
        f"- Folder: {payload['folder']}\n"
        f"- Type: {payload['extension']} ({payload['category']})\n"
        f"- Size: {payload['size']} bytes\n"
        + ("- NOTE: this file is marked sensitive; treat this carefully.\n" if payload["sensitive"] else "")
        + "\nQuestion: " + payload["question"] + "\n\n"
        "Answer in plain English as if helping someone who is not technical."
    )


def chatgpt_url(record, question):
    return (
        "https://chat.openai.com/?q="
        + urllib.parse.quote(_preface(_payload_record(record, question)), safe="")
    )


def gemini_url(record, question):
    return (
        "https://gemini.google.com/app?q="
        + urllib.parse.quote(_preface(_payload_record(record, question)), safe="")
    )


def claude_url(record, question):
    return (
        "https://claude.ai/new?q="
        + urllib.parse.quote(_preface(_payload_record(record, question)), safe="")
    )


def perplexity_url(record, question):
    return (
        "https://www.perplexity.ai/search?q="
        + urllib.parse.quote(_preface(_payload_record(record, question)), safe="")
    )


def compare_links(record, question):
    """Return [{platform, url}] in a stable order; question defaults to a
    generic 'what is this file' prompt."""
    question = (question or "").strip() or "What is this file and what does it do?"
    return [
        {"platform": "ChatGPT", "url": chatgpt_url(record, question)},
        {"platform": "Gemini", "url": gemini_url(record, question)},
        {"platform": "Claude", "url": claude_url(record, question)},
        {"platform": "Perplexity", "url": perplexity_url(record, question)},
    ]


def url_never_leaks_content(text):
    """Cheap guard: URLs in Mode A must never carry file contents. A test
    helper, also used by verify_build."""
    return "\nFile content:" not in text

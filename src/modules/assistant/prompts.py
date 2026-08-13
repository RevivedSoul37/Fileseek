from datetime import datetime

from ..core.utils import format_size

CODE_EXPLAINER = (
    "You are a friendly technical writer explaining code to a non-programmer. "
    "Use plain English and everyday analogies. Never use jargon without explaining it first. "
    "If you genuinely cannot tell what part of the code does, say so honestly. "
    "Aim for 120-220 words unless the content clearly needs more."
)

FILE_EXPLAINER = (
    "You are a friendly assistant explaining computer files to an everyday user. "
    "Use plain English and everyday analogies. Never use jargon without explaining it first. "
    "If you genuinely cannot tell what a file is for, say so honestly. "
    "Aim for 120-220 words unless the content clearly needs more."
)

DOC_SUMMARIZER = (
    "You are a friendly assistant summarizing documents for an everyday user. "
    "Use plain English, no jargon, analogies welcome. Give the gist first, then key points. "
    "If the document is unclear or incomplete, say so honestly. "
    "Aim for 120-220 words unless the content clearly needs more."
)

DOC_EXTENSIONS = {".md", ".txt", ".log"}

DEFAULT_QUESTION = "What is this file and what does it do?"


def select_prompt(category, extension):
    if category == "code":
        return CODE_EXPLAINER
    if (extension or "").lower() in DOC_EXTENSIONS and category == "document":
        return DOC_SUMMARIZER
    return FILE_EXPLAINER


def build_prompt(record, content, question, truncated):
    question = (question or "").strip() or DEFAULT_QUESTION
    lines = [
        f"File: {record.get('name', 'unknown')}",
        f"Folder: {record.get('parent_folder', 'unknown')}",
        f"Type: {record.get('extension', '') or 'no extension'} ({record.get('category', 'other')})",
        f"Size: {format_size(record.get('size', 0))}",
    ]
    if truncated:
        lines.append("Note: the file was too long, only the beginning is shown below.")
    lines.append("")
    lines.append("Question from the user: " + question)
    lines.append("")
    lines.append("File content:")
    lines.append(content or "(empty)")
    return "\n".join(lines)


def binary_answer(record):
    modified = record.get("modified")
    when = datetime.fromtimestamp(modified).strftime("%b %d, %Y at %H:%M") if modified else "unknown"
    return (
        f"This is a {record.get('extension') or 'file'} called {record.get('name', 'unknown')}. "
        f"It lives in the '{record.get('parent_folder', 'unknown')}' folder, weighs "
        f"{format_size(record.get('size', 0))}, and was last touched on {when}. "
        "Its contents are in a format I can't read as plain text, so that's the full "
        "picture from this machine's file catalog - nothing here was sent anywhere else."
    )

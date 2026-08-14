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

EXTRACTED_EXTENSIONS = {".pdf", ".docx"}

EXTRACTED_TEXT_NOTE = (
    "Note: the text below was machine-extracted from a structured document; "
    "pagination and formatting may be imperfect - read around missing pieces."
)

DEFAULT_QUESTION = "What is this file and what does it do?"

ASK_MORE_QUESTION = "Tell me more about this file, using what sits in its folder as clues."

ASK_MORE_SYSTEM = (
    "You are a friendly assistant in a conversation about one specific file on this computer. "
    "You are shown that file's details, the other files in its folder, and short excerpts from "
    "a few nearby text files. Use those siblings as clues to explain what this file is really for "
    "(for example, a metadata file next to a model file, or a config next to a script). "
    "Answer the latest question directly, in plain English, analogies welcome, no jargon. "
    "If the clues are not enough to be sure, say so honestly instead of guessing. "
    "Keep answers to 60-160 words unless the user asks for more."
)


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
    if (record.get("extension") or "").lower() in EXTRACTED_EXTENSIONS:
        lines.append(EXTRACTED_TEXT_NOTE)
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


def build_ask_more_system(record, content, truncated, context):
    lines = [
        ASK_MORE_SYSTEM,
        "",
        f"File: {record.get('name', 'unknown')}",
        f"Folder: {context.get('folder', record.get('parent_folder', 'unknown'))}",
        f"Type: {record.get('extension', '') or 'no extension'} ({record.get('category', 'other')})",
        f"Size: {format_size(record.get('size', 0))}",
    ]
    if truncated:
        lines.append("Note: the file itself was too long - only its beginning is shown (or nothing, if binary).")
    if content:
        lines.append("")
        lines.append("File content:")
        lines.append(content)
    siblings = context.get("siblings") or []
    if siblings:
        lines.append("")
        lines.append("Other files in this folder:")
        for sibling in siblings:
            lines.append(f"- {sibling['name']} [{sibling['category']}, {format_size(sibling['size'])}]")
    if context.get("hidden"):
        lines.append(f"(plus {context['hidden']} more files not listed)")
    for name, text in (context.get("excerpts") or {}).items():
        lines.append("")
        lines.append(f"Excerpt from neighbouring file {name}:")
        lines.append(text)
    return "\n".join(lines)

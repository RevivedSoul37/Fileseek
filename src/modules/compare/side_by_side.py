"""Phase 4, Mode B: in-app side-by-side cloud answers via API keys.

Deliberately a stub until someone provides keys — Mode A (free redirect) is
the shipped experience because the privacy contract is easier to honor when
nothing is fetched server-side. Keys would be read from environment variables
(FILESEEK_CHATGPT_KEY etc.) and NEVER written to disk.
"""

import os


def is_available():
    """Mode B is considered available only if at least one provider key is
    present in the environment. Off by default."""
    return any(
        os.environ.get(var)
        for var in ("FILESEEK_CHATGPT_KEY", "FILESEEK_GEMINI_KEY", "FILESEEK_CLAUDE_KEY")
    )


def compare_side_by_side(record, question):
    """The documented Mode-B socket. Returns {'available': False} until keys
    exist; callers must handle the disabled state gracefully."""
    return {"available": is_available(), "answers": []}

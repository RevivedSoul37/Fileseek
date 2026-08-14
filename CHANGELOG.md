# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT `LICENSE` file.
- `requirements.txt` now pins exact versions verified in the project venv
  (loose floors kept as comments).

## [1.1.0] - 2026-08-14

### Added
- Ask More: inline follow-up conversation about any file; the local model also sees
  folder context (up to 25 sibling files plus excerpts from up to 3 small nearby
  text files) so it can deduce what a file is really for.
- Full chat page (`/chat`): a dedicated ChatGPT-style conversation view per file
  with file header (icon, name, path, sensitive badge), bubble thread, composer,
  and automatic first question.
- Close (✕) button on Ask answer/chat panels; ⛶ Full chat launcher buttons.
- New endpoints: `POST /api/ask-more`, `GET /chat`, `GET /api/file-card`.
- `OllamaClient.chat()` — Ollama `/api/chat` support for multi-turn conversations.
- Verification suite extended to 59 checks, including a live ask-more smoke test.

### Changed
- `guide.md` documents Ask More, the full chat page, and the context caps.
- History sent to the model is trimmed server-side to the last 6 turns.

### Fixed
- None.

### Security
- Ask More stays 100% local: folder context is assembled in Python and only the
  capped excerpts are sent to the local Ollama instance.

## [1.0.0] - 2026-08-14

### Added
- Semantic file search over Downloads / Documents / Desktop (FAISS + MiniLM embeddings).
- Card catalog UI: category tabs, rubber-stamp match badges, sensitive badges,
  Open File / Open Folder actions.
- Live file watcher with per-card change-diff summaries (lines added/removed, size delta).
- Per-file Ask explainer backed by local Ollama (`llama3:8b` for documents,
  `qwen2.5-coder` for code), with truncation and binary metadata handling.
- Verification suite (`scripts/verify_build.py`) with live Ollama smoke test.

### Changed
- None (initial tagged baseline).

### Deprecated
- None.

### Removed
- None.

### Fixed
- None.

### Security
- Everything runs locally; no cloud calls in v1.0.0.

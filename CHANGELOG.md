# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-08-15

### Added
- Content search / RAG (Stage 7, opt-in): `content_index.py` embeds ~500-char
  windows of text-category files ≤256 KB into a second `IndexIDMap`
  (`data/content.index` + `content_meta.json`); `SearchEngine.search()` gains
  `scope=files|contents|both` with snippet-carrying cards; a scoped toggle
  sits left of search. The watcher keeps chunks current on create/modify/
  delete/move. Disabled by default behind the settings flag
  `content_index_enabled`.
- Settings UI + editable scan folders (removes the hardcoded SCAN_DIRS):
  `config.py` gains `load_settings()` / `save_settings()` / `apply_scan_dirs()`
  over `data/settings.json`; **⚙** masthead button opens a modal with
  add/remove path rows; `POST /api/config` validates the roots (must exist,
  no nesting, not the index dir), persists, stops the watcher and starts the
  re-index — progress shows in the ledger as before. Roots are applied at
  startup before the first scan.
- Activity feed (finishes the Phase 2 promise): a capped 200-entry ring
  (`modules/watcher/activity_log.py`) persisted to `data/activity.json`;
  `sync.py` appends one entry per applied watcher event (create/modify/delete/
  move/move-dir, with the diff stamp); `GET /api/activity?limit=` serves it
  newest-first; new **🕘 Activity** ledger toggle opens a side drawer that
  polls within the existing 4 s status cycle only while open.
- Ask's first question can be typed: the panel opens with an input row
  (*ask in your own words…*); empty falls back to the default question, and
  the typed question round-trips into the answer footer and the Ask More seed.
- Phase 5: Ask reads real PDF/DOCX contents. `content_reader.py` branches on
  extension — `pypdf` page text for `.pdf`, `python-docx` paragraphs for `.docx`,
  both capped at `ASK_MAX_CHARS` with the existing `[showing first ~N KB]` marker;
  unreadable/corrupt files fall back to the binary metadata summary.
- Prompt note for machine-extracted text (`EXTRACTED_TEXT_NOTE`) so the model
  knows pagination/OCR may be imperfect.
- New pinned dependencies: `pypdf==6.16.1`, `python-docx==1.2.0`.
- Phase 4, Compare Mode A: `modules/compare/platforms.py` builds opt-in
  redirect URLs for ChatGPT / Gemini / Claude / Perplexity; payload = file
  name/type/size + question only, content never leaves the machine.
- `modules/compare/side_by_side.py` — the documented Mode-B (env-var API key)
  socket, returns `{"available": False}` until keys exist.
- `POST /api/compare` endpoint; ☁ Compare button in the Ask answer footer,
  inline chat, and the full chat page header (red opt-in styling, sensitive
  confirmation on the catalog).
- MIT `LICENSE` file; `requirements.txt` pinned to exact venv versions (loose
  floors kept as comments).
- Graceful shutdown: Ctrl+C / console close stops the watcher and saves the
  index and snapshots immediately instead of waiting for the 30 s interval.
- Security model documented (localhost bind, path validation, no auth by design)
  in README and guide.

### Changed
- Roadmap: Phase 4 Compare marked done; README and guide document ☁ Compare.

### Security
- `/api/open/file` and `/api/open/folder` now validate that the requested
  path is inside a scan root (or already indexed) before opening — 403 outside.

### Fixed
- README stat drift (`13,489` vs live index) and the reindex button label
  overwrite in `app.js` (now keeps `🔄 Refile everything`).
- Deleted stale local branch `brief-caption`.

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

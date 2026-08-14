# FileSeek — Usage Guide

## Starting
Double-click `run.bat`. On first run it creates a virtual environment and installs
dependencies (needs internet once). After that, it opens http://127.0.0.1:7860
in your browser automatically.

## Searching
- Press `Ctrl+K` anywhere to jump to the search bar.
- Search by **meaning**: typing `resume` finds `CV.pdf`, typing `video editing`
  finds `.mp4` files and workflow JSONs.
- Exact words and partials work too — the ranker boosts files whose names
  literally contain your query.
- Filter by type with the pills under the search bar (Docs / Images / Media / Code / Archives / Data).
- Every result shows a match %, the semantic similarity, size, and last modified time.

## Results
- **Open File** — launches the file in its default application.
- **Open Folder** — opens Explorer with that file selected.
- **Ask** — a local AI reads the file and explains it in plain English (see below).
- Files whose names match sensitive patterns (api keys, tokens, backup codes, etc.)
  get a 🔒 `sensitive` badge so you can spot them in search results.
  Note: the badge is a heads-up only — the file is still openable.

## Ask (per-file explainer)
Click **Ask** on any result card. A local Ollama model reads the file and writes a
plain-language explanation right on the card — no jargon, honest about unknowns.

The panel opens with one input row: *ask in your own words…* Type your own
question and submit, or press **📮 Ask** with it empty to use the default
("What is this file and what does it do?"). Your question round-trips into the
answer footer and seeds the Ask More / Full chat conversation.

- **Code files** (`.py`, `.js`, `.ts`, etc.) are explained by `qwen2.5-coder`;
  everything else by `llama3:8b`.
- **PDF and Word files** (`.pdf`, `.docx`) get their text extracted locally
  (`pypdf` / `python-docx`) before the model reads them (Phase 5). Extraction is
  capped like plain text (~8 KB); a corrupt or unreadable document falls back to
  the metadata summary.
- **Very large files** are read up to the first ~8 KB only; the answer panel notes
  when a file was truncated.
- **Binary files** (images, videos, zips…) get an instant metadata summary
  (name, size, type, last modified) — no model call, no waiting.
- **Sensitive files** show a red "marked sensitive" stamp in the answer panel:
  reviewed locally only, nothing leaves this machine.
- Click **Ask** again to fold the answer away.
- Models, timeout, and read cap live in `src/modules/core/config.py`
  (`OLLAMA_MODEL`, `OLLAMA_CODE_MODEL`, `ASK_TIMEOUT_SECONDS`, `ASK_MAX_CHARS`).

### Ask requirements
- [Ollama](https://ollama.com) running on this machine (`ollama serve`), with:
  - `ollama pull llama3:8b`
  - `ollama pull qwen2.5-coder`
- When the status pill shows **ask ready**, Ask is live. If Ask is offline the
  button still works — it answers instantly for binary files and shows a friendly
  error card for text files until Ollama is running.
- The first ask after a while can take a few extra seconds while the model loads
  into VRAM; the model stays warm afterward.

## Ask More (conversation with folder clues)
After an Ask answer, click **💬 Ask more** in the answer footer to open an inline
chat about that file. The model now also sees:
- the other files in the same folder (up to 25 siblings, names/sizes/types), and
- short excerpts from up to 3 small nearby text files (≤1.5 KB each)

…so it can reason about what the file actually is — e.g. a `metadata.json` sitting
next to model files, or a config sitting next to a script. Works great for binary
files too, since those get their meaning from what is around them.

- History is kept in the card only (last 6 turns are sent to the model, oldest dropped).
- The chat footer shows the model stamp and how many folder clues were used.
- Caps live in `src/modules/core/config.py`: `ASK_MORE_MAX_SIBLINGS`,
  `ASK_MORE_EXCERPT_FILES`, `ASK_MORE_EXCERPT_CHARS`, `ASK_MORE_MAX_TURNS`.
- Folder context is assembled in Python — listing siblings never calls the model;
  only each question you send does.
- **✕** closes the answer/chat panel on a card.
- **⛶ Full chat** opens a dedicated conversation page (like ChatGPT) for that file:
  full-height thread, composer at the bottom, file header with name/path and
  sensitive badge. It opens with an automatic first question and keeps the same
  folder-clue context. Use **← catalog** to go back.

## Compare with Cloud AI (☁, opt-in)
From the Ask answer footer, the inline chat, or the full chat header, click
**☁ Compare**. FileSeek opens **ChatGPT, Gemini, Claude and Perplexity** in new
tabs with the question pre-filled. This is Mode A (free redirect) — no API keys,
and the payload is **only the file's name, type and size plus your question**:
the file's *content never leaves the machine*. Sensitive files prompt an extra
confirmation. Compare needs no Ollama and no index entry.

## Indexing
- The index builds automatically on first launch (scans Downloads, Documents, Desktop).
- The status bar shows file count and when the index was last built.
- Click **🔄 Refile everything** to force a full rescan (e.g. after moving lots of files).
- The watcher keeps the index current in real time after a successful index load/build.
- The index lives in `data/` and loads instantly on subsequent launches.

## What gets scanned
- `C:\Users\liter\Downloads`, `Documents`, `Desktop`
- Skipped automatically: `node_modules`, `.git`, `__pycache__`, `venv`, `.venv`,
  `AppData`, `$Recycle Bin`, caches, and build folders.

## Privacy
Everything runs locally. Search embeddings, the watcher, and Ask all stay on this
machine — Ask talks only to `http://127.0.0.1:11434` (local Ollama), never the cloud.
(The Phase 4 "Compare with Cloud AI" feature will be opt-in and clearly labeled.)

**Security model:** the server binds to `127.0.0.1` only (no LAN/internet access),
has no authentication by design, and refuses to open paths outside the configured
scan roots.

## Phases (roadmap)
1. ✅ Semantic search — meaning-based search over Downloads/Documents/Desktop
2. ✅ Live file watcher — index updates itself in real time; cards show what changed
3. ✅ Plain-language assistant — Ask button explains any file via local Ollama
4. ✅ Compare with Cloud AI — opt-in ☁ second opinion (name/type/size only, never content)
5. ✅ Ask over PDF/DOCX contents — `pypdf` + `python-docx` extraction feeds Ask

## Troubleshooting
- **Search says "building your index…" for a long time** — first index of a large
  folder takes ~20s per 10k files. Watch the progress text in the status bar.
- **Ask says Ollama is not running** — start Ollama (system tray app or `ollama serve`),
  then click Ask again. No restart of FileSeek needed.
- **Ask says a model is not downloaded** — run the `ollama pull …` command shown
  in the error message, then retry.
- **Ask takes a long time the first try** — the model is loading into VRAM
  (a few seconds on the RTX 5070 Ti); later asks are much faster. If an answer
  ever exceeds 60 it times out with a clear message — raise
  `ASK_TIMEOUT_SECONDS` in `config.py` if needed.
- **Port already in use** — change `PORT` in `src/modules/core/config.py`.
- **Something broke** — delete the `data\` folder and double-click `run.bat` to rebuild.

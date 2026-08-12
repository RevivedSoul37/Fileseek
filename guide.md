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
- Files whose names match sensitive patterns (api keys, tokens, backup codes, etc.)
  get a 🔒 `sensitive` badge so you can spot them in search results.
  Note: the badge is a heads-up only — the file is still openable.

## Indexing
- The index builds automatically on first launch (scans Downloads, Documents, Desktop).
- The status bar shows file count and when the index was last built.
- Click **🔄 Re-index** to force a full rescan (e.g. after moving lots of files).
- The index lives in `data/` and loads instantly on subsequent launches.

## What gets scanned
- `C:\Users\liter\Downloads`, `Documents`, `Desktop`
- Skipped automatically: `node_modules`, `.git`, `__pycache__`, `venv`, `.venv`,
  `AppData`, `$Recycle Bin`, caches, and build folders.

## Privacy
Everything runs locally. Your file names and contents never leave this computer.
(The Phase 4 "Compare with Cloud AI" feature will be opt-in and clearly labeled.)

## Phases (roadmap)
1. ✅ Semantic search (this build)
2. 🔜 Live file watcher — index updates itself in real time (watchdog)
3. 🔜 Plain-language assistant — ask "what does this file do?" via local LLM (Ollama)
4. 🔜 Compare with Cloud AI — opt-in second opinion from ChatGPT/Gemini/Claude

## Troubleshooting
- **Search says "building your index…" for a long time** — first index of a large
  folder takes ~20s per 10k files. Watch the progress text in the status bar.
- **Port already in use** — change `PORT` in `src/modules/core/config.py`.
- **Something broke** — delete the `data\` folder and double-click `run.bat` to rebuild.

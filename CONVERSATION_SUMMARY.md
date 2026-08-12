# Conversation Log & Project Overview — FileSeek

**Session Date:** August 12, 2026  
**Project Folder:** `C:\Users\liter\Desktop\FileSeek\`  
**Target Application:** FileSeek (Local AI Semantic File Search & Intelligence Assistant)

---

## 📑 1. Summary of Session Activities

During this session, we accomplished two major milestones:
1. **Downloads Folder Organization:** Automated clean-up and classification of ~310 loose items into structured numbered directories with zero data loss and full audit logging.
2. **FileSeek Product Strategy & Architectural Design:** Designed a complete 4-phase local AI file search, monitoring, and RAG assistant application tailored for non-technical users running local hardware.

---

## 🗂️ 2. Downloads Folder Organization Summary

- **Total Items Processed:** 310 items (loose files & directories).
- **Errors / Data Loss:** 0 errors.
- **Log Location:** `C:\Users\liter\Downloads\ORGANIZE_LOG.txt`
- **Categorization Scheme Applied:**
  - `01-Installers/` — `.exe`, `.msi` setup packages
  - `02-Images/` — `.png`, `.jpg`, `.jpeg`, `.webp`, `.avif`, `.svg`
  - `03-Projects/` — CreativeOS, Battleground Evolved, story bibles, spec docs
  - `04-Documents/` — PDFs, manuals, resumes, reports, text extracts
  - `05-Archives/` — `.zip`, `.7z`, `.torrent` archives
  - `06-Media/` — `.mp4`, `.mp3`, `.m4a`, `.wav`, `.flac` audio/video
  - `07-Code/` — `.py`, `.jsx`, `.json` workflows, `.html` dashboards
  - `07-Folders/` — Nested project subdirectories
  - `08-Data/` — `.csv`, `.xlsx`, datasets
- **Security & Hygiene Flags:** Identified sensitive credential files (API keys, backup codes) in `04-Documents/` and ~700 MB of duplicate installer files (`Wispr Flow`, `Hermes`).

---

## 💡 3. The FileSeek Product Concept & Discussion Highlights

### The Problem
Windows Explorer file search is slow, rigid, and strictly relies on exact character matches. Finding files without knowing their exact name leads to frustration.

### The Solution: FileSeek
A 100% on-device semantic file search tool powered by local AI vector embeddings (`sentence-transformers` + `FAISS`). It converts filenames and paths into "meaning vectors" so searching "resume" retrieves "CV.pdf" or "job_application.docx".

---

## 🗣️ Key Strategic Discussions & Pivots

### A. RAG vs. Fine-Tuning a Coder LLM
- **Question:** Should we fine-tune a coding LLM or build a RAG system to explain technical files in plain language?
- **Conclusion:** **RAG + Prompt Engineering is superior.** Fine-tuning is costly, prone to hallucinations without grounding, and hard to update. RAG ensures 100% factual accuracy grounded in actual file contents.

### B. Real-Time File System Integration ("Living Index")
- **Concept:** Instead of manual re-indexing, FileSeek will hook into Windows native `ReadDirectoryChangesW` via Python `watchdog`.
- **Behavior:** Automatically updates vector embeddings whenever files are created, renamed, moved, or deleted. Offers a live "Activity Timeline".

### C. Safety & Permission Tiers for Non-Technical Users
- **Challenge:** Giving AI read/write access to OS files poses safety risks.
- **Solution:** Enforce 4 Security Tiers:
  1. *Read-Only (Tier 1)*: Information lookup — always safe, no prompts.
  2. *Safe Write (Tier 2)*: Organizing files — user approves once.
  3. *Careful Write (Tier 3)*: Renaming/moving — explicit user confirmation.
  4. *Blocked Tier*: Formatting/system paths — physically prohibited in code.

### D. "Compare Answer" Trust Builder
- **Innovation:** A bottom action bar in the UI with a "Compare with Cloud AI" button.
- **Modes:**
  - *Redirect Mode (Free)*: Opens ChatGPT/Gemini/Claude in browser with pre-filled prompt.
  - *Side-by-Side Mode (API)*: Fetches cloud response and displays agreement score (Green/Yellow/Red confidence badge).

### E. Data Extraction Clarification
- **Confirmed:** Data extraction occurs at Phase 1 via `crawler.py` (file metadata collection) → `embedder.py` (vector generation) → `index_store.py` (FAISS persistence).

---

## 🖥️ 4. System Specs Verified

| Hardware / Tool | Specification / Status | Notes |
|---|---|---|
| **GPU** | NVIDIA GeForce RTX 5070 Ti (16 GB VRAM) | Excellent capacity for local LLM inference |
| **Storage** | 160 GB Free on C: | Ample room for indices & models |
| **Python** | 3.11.15 | Active environment |
| **Ollama** | Installed | `C:\Users\liter\AppData\Local\Programs\Ollama\ollama.exe` |
| **watchdog** | Version 6.0.0 | Active |
| **sentence-transformers** | Installed | Active |
| **faiss-cpu** | Pending | Will install on initialization |

---

## 🏗️ 5. The 4-Phase Roadmap

```
┌─────────────────────────────────────────────────────────┐
│ PHASE 4: Compare with Cloud AI                          │
│ Trust layer with ChatGPT / Gemini / Claude cross-check  │
├─────────────────────────────────────────────────────────┤
│ PHASE 3: RAG + Plain Language Assistant                 │
│ Local LLM (Ollama + Llama 3.2 3B) explaining code/docs │
├─────────────────────────────────────────────────────────┤
│ PHASE 2: Live File Watcher                              │
│ Real-time event monitoring via watchdog                 │
├─────────────────────────────────────────────────────────┤
│ PHASE 1: Semantic File Search                           │
│ Local embedding vector search via FAISS + Flask UI      │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 6. Desktop Folder Contents (`C:\Users\liter\Desktop\FileSeek\`)

1. **`implementation_plan.md`**: Complete, unabridged architectural design, file structure, module responsibilities, verification steps, and plain-language technical glossary.
2. **`CONVERSATION_SUMMARY.md`**: (This file) Chronological summary of discussions, decisions, system checks, and project roadmap.

---

## 🎯 7. Next Actions for Implementation

1. Initialize project folder structure in `C:\Users\liter\Documents\antigravity\eager-raman\fileseek\`.
2. Set up virtual environment and install `faiss-cpu`.
3. Implement core modules (`config.py`, `utils.py`, `crawler.py`, `embedder.py`, `index_store.py`, `engine.py`, `ranker.py`).
4. Build Flask web server (`app.py`) and single-page dark UI (`index.html`, `style.css`, `app.js`).
5. Generate `run.bat` double-click script and execute verification tests.

---

## ✅ 8. PHASE 1 BUILT & VERIFIED (Session 2 — Aug 12, 2026)

All 7 next-actions above were executed. Phase 1 is complete and working.

- **Project location:** ~~`C:\Users\liter\Documents\antigravity\eager-raman\fileseek\`~~ **MOVED (Session 4)** — everything now lives in `C:\Users\liter\Desktop\FileSeek\` (docs + backend + frontend + venv + data in one folder; see §10)
- **Environment:** Dedicated `venv` (Python 3.11.15, `--system-site-packages` to reuse existing CPU torch); installed flask 3.1.3, faiss-cpu 1.15.0, sentence-transformers 5.7.0, watchdog, requests. torch is CPU-only — irrelevant for FAISS flat-index scale; GPU matters again at Phase 3 (Ollama).
- **Verification suite (`verify_build.py`): 26/26 checks passed** — utils unit tests, crawler (13,461 files in 0.8s), embedding ((13461, 384) L2-normalized, 48.5s), index build/save/reload, 5 semantic searches (8–10ms each), incremental add/remove (`IndexIDMap` — Phase-2 ready), category filtering.
- **Live HTTP tests passed:** `/api/status`, `/api/config`, `/api/search` all return correct data on port 7860.
- **Ranker fix applied during build:** initial ranking put `regression-…-resume.test.ts` above `Resume.pdf` for query "resume" — exactly the failure mode the plan anticipated. Fixed by making the exact-match weight *coverage-based* (query length vs filename-stem length): `Resume.pdf` now rank #1 at 55%.
- **Sensitive-file tagging implemented:** files matching markers (api key, token, backup code, .pem, .key, etc.) get a 🔒 badge in the UI. Heads-up only — files remain openable.
- **Index stats:** 13,461 files — document 2,751 · code 2,712 · data 5,617 · image 1,563 · media 254 · other 519 · archive 45.

**To start:** double-click `run.bat` → browser opens http://127.0.0.1:7860. `Ctrl+K` focuses search. See `guide.md` for usage.

**Remaining for future sessions:** Phase 2 (`watcher/` — monitor.py, event_queue.py, sync.py), Phase 3 (`assistant/` — Ollama RAG), Phase 4 (`compare/`).

---

## 🎨 9. UI REDESIGN — "THE NIGHT-SHIFT CARD CATALOG" (Session 3)

Redesigned under the Anthropic `frontend-design` skill (copied into
`fileseek/docs/skills/frontend-design/` with LICENSE).

**Identity:** FileSeek IS a card catalog ("like a library card catalog, but organized by
meaning" — from its own plan doc), so the UI became one literally: a deep lacquer-green
reading room at night; results are aged-paper index cards with a red header rule and two
punched holes; drawers are the category tabs with live file counts.

- **Palette (6 tokens):** lacquer #0E1915 · drawer #15221C · rail #263B2F · paper #F3ECD9 · brass #C9A227 · stamp #B3402E
- **Type:** Fraunces (display) · Karla (body) · IBM Plex Mono (utility)
- **Signature:** the rubber-stamp match mark — tilted, ink-colored, stamp-down animation
- **Quality floor:** responsive <720px, visible focus rings, prefers-reduced-motion honored
- Verified by headless-Edge screenshots; fixed during critique: transparent buttons over the
  red rule (now paper-backed), stale-template server caching, an HTML quote typo.

**TEST_PLAN.md → TEST_PLAN.html** (`Desktop\FileSeek\TEST_PLAN.html`): same token system,
inverted composition — a paper protocol sheet on the lacquer desk. The signature stamp IS the
interaction: click any of the 51 check rows and a red PASSED stamp slams down; a live tally
counts stamps; state persists in localStorage. Numbered TIER markers retained because the
content is genuinely sequential.

---

## 📦 10. PROJECT CONSOLIDATION (Session 4 — Aug 12, 2026)

Everything moved into **one folder: `C:\Users\liter\Desktop\FileSeek\`**

- Backend (`src\modules\...`), frontend (`src\static`, `src\templates`), `run.bat`,
  `guide.md`, `verify_build.py`, `requirements.txt`, `data\`, `docs\skills\` and all
  planning docs now share this directory. The old `antigravity\eager-raman\fileseek`
  folder was deleted after a verified 26/26-file copy.
- `venv\` was rebuilt at the new path (venvs hardcode absolute paths); all deps re-verified.
- Full re-index ran from the new location: **13,489 files, 0 stale paths**.
- Config change: removed the blanket `EXCLUDE_PATHS` self-exclusion — the app's own folder
  is now indexed too (its planning docs are searchable; junk dirs stay excluded by name).
  The 1,055 "antigravity" files in the index are your *other* projects under
  `Documents\antigravity` — legitimate scan targets, not leftovers.

# FileSeek — Local AI File Intelligence System

> **STATUS (Aug 12, 2026): PHASE 1 BUILT ✅** — 26/26 verification checks passed, 13,461 files indexed, live on `http://127.0.0.1:7860`. See `CONVERSATION_SUMMARY.md` §8 for build details. Launch: double-click `run.bat` in `C:\Users\liter\Desktop\FileSeek\`.


## 📋 Quick Summary

**What is this?** A tool that runs 100% on your computer and helps you find, understand, and manage your files using AI — like having a smart assistant for your file system.

**What makes it special?**
- Search files by **meaning**, not just exact name (search "resume" → finds "CV.pdf")
- **Always up-to-date** — watches your files in real-time
- **Explains things simply** — ask "what does this code do?" in plain English
- **Cross-check answers** with ChatGPT/Gemini/Claude for trust
- **100% local** — nothing leaves your computer, no internet needed
- **One click to start** — just double-click `run.bat`

---

## 🖥️ Your System (Verified)

| Component | Status | Details |
|---|---|---|
| GPU | ✅ RTX 5070 Ti | 16 GB VRAM — more than enough |
| Disk | ✅ 160 GB free | Only need ~500 MB for FileSeek |
| Python | ✅ 3.11.15 | Perfect |
| Ollama | ✅ Installed | For running local LLM (Phase 3) |
| sentence-transformers | ✅ Installed | For generating embeddings |
| watchdog | ✅ v6.0.0 | For watching file changes (Phase 2) |
| Flask | ✅ v3.1.3 | For the web server |
| faiss-cpu | ❌ Needs install | Vector search engine — will install automatically |

---

## 🏗️ The Big Picture — 4 Phases

Think of this like building a house. Each phase adds a floor:

```
┌─────────────────────────────────────────────────┐
│  PHASE 4: Compare with Cloud AI                 │  ← Trust layer
│  "Get a second opinion from ChatGPT/Gemini"     │
├─────────────────────────────────────────────────┤
│  PHASE 3: RAG + Plain Language Assistant        │  ← Brain layer
│  "What does this file do? Explain simply."      │
├─────────────────────────────────────────────────┤
│  PHASE 2: Live File Watcher                     │  ← Eyes layer
│  "Auto-detect every file change in real-time"   │
├─────────────────────────────────────────────────┤
│  PHASE 1: Semantic File Search  ◄── BUILD NOW   │  ← Foundation
│  "Find any file by meaning, instantly"          │
└─────────────────────────────────────────────────┘
```

**We build Phase 1 now.** Each later phase plugs into it without breaking anything.

---

## 📁 Project Structure

```
C:\Users\liter\Desktop\FileSeek\
│
├── 📄 run.bat                          # Double-click to start everything
├── 📄 guide.md                         # Plain-English usage guide
├── 📄 requirements.txt                 # Python packages needed
│
├── 📂 src/                             # All source code lives here
│   │
│   ├── 📄 app.py                       # The main server (the "brain stem")
│   │
│   ├── 📂 modules/                     # Feature modules (organized by function)
│   │   │
│   │   ├── 📂 core/                    # Shared utilities used everywhere
│   │   │   ├── 📄 config.py            # Settings: which folders to scan, ports, etc.
│   │   │   └── 📄 utils.py             # Helper functions: file icons, size formatting
│   │   │
│   │   ├── 📂 indexer/                 # PHASE 1: Turns files into searchable data
│   │   │   ├── 📄 crawler.py           # Walks your folders, collects file info
│   │   │   ├── 📄 embedder.py          # Converts file names to AI "fingerprints"
│   │   │   └── 📄 index_store.py       # Stores & manages the search database
│   │   │
│   │   ├── 📂 search/                  # PHASE 1: Finds files from your queries
│   │   │   ├── 📄 engine.py            # The search logic
│   │   │   └── 📄 ranker.py            # Makes results smarter (exact match boost, etc.)
│   │   │
│   │   ├── 📂 watcher/                 # PHASE 2 (future): Real-time file monitoring
│   │   │   ├── 📄 monitor.py           # Watches for file changes
│   │   │   ├── 📄 event_queue.py       # Queues changes for processing
│   │   │   └── 📄 sync.py              # Updates the index when files change
│   │   │
│   │   ├── 📂 assistant/               # PHASE 3 (future): AI chat + RAG
│   │   │   ├── 📄 llm_client.py        # Talks to Ollama (local LLM)
│   │   │   ├── 📄 rag_pipeline.py      # Retrieves relevant file chunks
│   │   │   ├── 📄 content_reader.py    # Reads inside documents (PDF, TXT, DOCX)
│   │   │   └── 📄 prompts.py           # System prompts for plain-language output
│   │   │
│   │   └── 📂 compare/                 # PHASE 4 (future): Cross-AI verification
│   │       ├── 📄 platforms.py          # URL builders for ChatGPT/Gemini/Claude
│   │       └── 📄 side_by_side.py       # Optional API-based comparison
│   │
│   ├── 📂 static/                      # Frontend assets (what makes it look good)
│   │   ├── 📄 style.css                # All the visual design
│   │   └── 📄 app.js                   # Search interactions, animations
│   │
│   └── 📂 templates/                   # HTML pages
│       └── 📄 index.html               # The main search page
│
└── 📂 data/                            # Auto-generated data (don't edit these)
    ├── 📄 fileseek.index               # The FAISS search database
    └── 📄 metadata.json                # File info cache (names, paths, sizes, dates)
```

---

## 🔨 PHASE 1: Semantic File Search (Building Now)

### What It Does
You type a query → it instantly finds matching files by **meaning**, not just name.

### How Each Module Works

---

#### `src/modules/core/config.py` — Settings

Think of this as the "control panel." It defines:

```
DEFAULT FOLDERS TO SCAN:
  - C:\Users\liter\Downloads
  - C:\Users\liter\Documents
  - C:\Users\liter\Desktop

FOLDERS TO SKIP (always ignored):
  - node_modules       (huge, useless for search)
  - .git               (internal git data)
  - __pycache__         (Python cache)
  - .venv               (virtual environments)
  - AppData             (system junk)

SETTINGS:
  - Server port: 7860
  - Max results: 20
  - Embedding model: all-MiniLM-L6-v2
  - Index file location: data/fileseek.index
```

---

#### `src/modules/core/utils.py` — Helpers

Small utility functions used everywhere:

| Function | What It Does | Example |
|---|---|---|
| `format_size(bytes)` | Makes file sizes readable | `1048576` → `"1.0 MB"` |
| `get_file_icon(extension)` | Maps file types to emoji | `.pdf` → `📄`, `.mp4` → `🎬` |
| `get_file_category(extension)` | Groups files into types | `.jpg` → `"image"`, `.py` → `"code"` |
| `time_ago(timestamp)` | Human-readable dates | `"2 hours ago"`, `"yesterday"` |

---

#### `src/modules/indexer/crawler.py` — File Discovery

**What it does:** Walks through your chosen folders and collects info about every file.

**How it works (simplified):**
```
1. Start at C:\Users\liter\Downloads
2. Look at every file:
   - Name: "Resume.pdf"
   - Path: "C:\Users\liter\Downloads\04-Documents\Resume.pdf"
   - Size: 53,787 bytes
   - Modified: 2026-07-15
   - Type: "document"
3. Skip folders in the exclusion list (node_modules, .git, etc.)
4. Return a list of ALL files found
```

**What it collects per file:**
| Field | Example | Why We Need It |
|---|---|---|
| `name` | Resume.pdf | For display + embedding |
| `path` | C:\Users\...\Resume.pdf | For opening the file |
| `parent_folder` | 04-Documents | For context in embedding |
| `extension` | .pdf | For filtering + icon |
| `size` | 53787 | For display |
| `modified` | 2026-07-15 | For recency ranking |
| `category` | document | For filter buttons |

---

#### `src/modules/indexer/embedder.py` — The AI Fingerprinter

**What it does:** Converts each file's info into a list of numbers (an "embedding") that captures its *meaning*.

**Why this works (simple analogy):**
Imagine every word and concept lives on a huge map. "Resume" and "CV" are right next to each other on this map because they mean similar things. "Cat video" is far away from both. The embedding is basically the GPS coordinates of each file on this meaning-map.

**What gets embedded per file:**
```
Input text: "Resume.pdf Documents pdf document personal"
                ↓
AI model processes it
                ↓
Output: [0.23, -0.87, 0.45, 0.12, ... ] (384 numbers)
```

The clever part: we don't just embed the filename. We build a rich text string:
- `"Resume.pdf"` — the name
- `"Documents"` — the parent folder (adds context)
- `"pdf document"` — what the extension means in words

This way, searching "job application" can still find "Resume.pdf" because the model understands the connection.

**Model used:** `all-MiniLM-L6-v2`
- Size: ~22 MB (tiny)
- Speed: ~2ms per file name
- Quality: Excellent for short text matching
- 10,000 files = ~20 seconds to index

---

#### `src/modules/indexer/index_store.py` — The Search Database

**What it does:** Stores all the embeddings in a FAISS index for lightning-fast lookup.

**FAISS explained simply:**
Think of it like a library card catalog, but instead of alphabetical order, it's organized by *meaning*. When you search, it doesn't check every single card — it jumps straight to the right neighborhood.

**What gets saved:**
1. `data/fileseek.index` — The FAISS index (all the number-fingerprints)
2. `data/metadata.json` — The actual file info (names, paths, sizes, dates)

**Key operations:**
| Operation | What It Does | When It's Used |
|---|---|---|
| `build_index()` | Creates the index from scratch | First run, or manual re-index |
| `add_file()` | Adds one new file | Phase 2: when a file is created |
| `remove_file()` | Removes one file | Phase 2: when a file is deleted |
| `update_file()` | Re-embeds a renamed/moved file | Phase 2: when a file changes |
| `save()` / `load()` | Persists to disk / loads from disk | Startup and shutdown |

---

#### `src/modules/search/engine.py` — The Search Brain

**What it does:** Takes your search query, converts it to an embedding, and finds the closest matches in the FAISS index.

**How a search works step-by-step:**
```
You type: "cricket data"
     ↓
1. Convert "cricket data" → embedding [0.15, -0.92, 0.33, ...]
     ↓
2. Ask FAISS: "find me the 20 files closest to these numbers"
     ↓
3. FAISS returns matches with similarity scores:
   - IPL_2026_Analysis.csv           → 0.89 similarity
   - IPL_2026_Intelligence_Dossier.csv → 0.87 similarity
   - stats_India.json                 → 0.82 similarity
   - Trend Hunter — India.xlsx        → 0.71 similarity
     ↓
4. Pass results to the ranker for final ordering
```

**Speed:** This entire process takes **< 50 milliseconds**, even with 100,000+ files indexed.

---

#### `src/modules/search/ranker.py` — Smart Result Ordering

**What it does:** The raw FAISS results are good but not perfect. The ranker adjusts the order using common sense:

| Factor | Weight | Example |
|---|---|---|
| **Semantic similarity** | 60% | How closely the meaning matches |
| **Exact substring match** | 25% | If the query text appears literally in the filename |
| **Recency** | 10% | Newer files get a small boost |
| **File size relevance** | 5% | Non-empty files rank higher than 0-byte files |

**Why this matters:**
Without the ranker, searching "Resume" might show a random image named "resume_background.png" above your actual "Resume.pdf" because the embedding similarity was slightly higher. The ranker says "wait, the word 'Resume' is literally in 'Resume.pdf' — boost that one up."

---

#### `src/app.py` — The Server

**What it does:** Runs the web server that connects the frontend (what you see) with the backend (the search logic).

**API Routes (the "doors" into the system):**

| Route | Method | What It Does |
|---|---|---|
| `/` | GET | Serves the main search page |
| `/api/search` | POST | Runs a search and returns results |
| `/api/index` | POST | Triggers a full re-index |
| `/api/status` | GET | Returns index stats (file count, last indexed, etc.) |
| `/api/open/file` | POST | Opens a file in its default app |
| `/api/open/folder` | POST | Opens the file's parent folder in Explorer |
| `/api/config` | GET | Returns current settings |

---

#### `src/templates/index.html` + `src/static/style.css` + `src/static/app.js` — The UI

**Design vision:** Premium dark theme that feels like a professional tool, not a homework project.

**UI sections:**
```
┌──────────────────────────────────────────────────────────┐
│  ┌────────────────────────────────────────────────────┐  │
│  │  🔍  Search your files...                    ⚙️   │  │ ← Glowing search bar
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Filter: [All] [📄 Docs] [🖼️ Images] [🎬 Media]        │ ← Type filters
│          [💻 Code] [📦 Archives] [📊 Data]               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 📄 Resume.pdf                           95% match │  │ ← Result card
│  │    C:\Users\liter\Downloads\04-Documents           │  │
│  │    53.7 KB · Modified 3 weeks ago                  │  │
│  │    [Open File] [Open Folder]                       │  │
│  ├────────────────────────────────────────────────────┤  │
│  │ 📄 Aether_Bound_Game_Design_v2.docx     82% match │  │
│  │    C:\Users\liter\Downloads\03-Projects            │  │
│  │    21.1 KB · Modified 2 months ago                 │  │
│  │    [Open File] [Open Folder]                       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ── Index: 2,847 files · Last indexed: 2 minutes ago ── │ ← Status bar
│  [🔄 Re-index Now]                                      │
└──────────────────────────────────────────────────────────┘
```

**Key UI behaviors:**
- **Real-time search** — Results appear as you type (with a 300ms delay so it doesn't search every keystroke)
- **Click "Open File"** — Opens the file in its default application (PDF in viewer, images in photo viewer, etc.)
- **Click "Open Folder"** — Opens File Explorer at that file's location with the file highlighted
- **Filter buttons** — Click to show only images, only documents, etc.
- **Keyboard shortcuts** — `Ctrl+K` focuses the search bar from anywhere

---

## 🔮 PHASE 2: Live File Watcher (Future)

> [!NOTE]
> **Not building now** — this gets added after Phase 1 is solid.

### What It Adds
A background process that watches your folders and automatically updates the search index whenever you create, move, rename, or delete files.

### How It Plugs In
```
Phase 1 (current):  You search → results from last index
Phase 2 (added):    Files change → index auto-updates → search always current
```

### Key Modules

| File | Purpose |
|---|---|
| `watcher/monitor.py` | Uses `watchdog` library to listen for file system events (create, delete, rename, move) |
| `watcher/event_queue.py` | Collects rapid-fire events into batches (so renaming 100 files doesn't overwhelm the system) |
| `watcher/sync.py` | Processes the event queue and updates the FAISS index incrementally |

### Activity Feed Addition
The UI gets a new tab showing recent file activity:
```
📋 Recent Activity
─────────────────
🕐 2 min ago   📝 Created "project_notes.md" in Documents
🕐 5 min ago   📦 Moved "report.pdf" from Downloads → Documents
🕐 12 min ago  ✏️ Renamed "untitled.txt" → "meeting_notes.txt"
```

---

## 🔮 PHASE 3: RAG + Plain Language Assistant (Future)

> [!NOTE]
> **Not building now** — requires Phase 1 + Phase 2 as foundation.

### What It Adds
An AI chat interface where you can ask questions about your files in plain English and get simple, jargon-free answers.

### How It Works
```
You: "What does the viral_score.py file do?"

System (behind the scenes):
  1. Searches the index for "viral_score.py"
  2. Reads the actual file contents
  3. Sends the content + your question to local LLM (via Ollama)
  4. LLM explains it in plain English

AI: "This is a Python script that calculates how likely a social
     media post is to go viral. It looks at things like word count,
     emoji usage, and hashtag count, then gives each post a score
     from 0 to 100. Higher score = more likely to go viral."
```

### Key Modules

| File | Purpose |
|---|---|
| `assistant/llm_client.py` | Connects to Ollama to run a local LLM (Llama 3.2 3B or Phi-3) |
| `assistant/rag_pipeline.py` | Retrieves relevant file chunks and builds context for the LLM |
| `assistant/content_reader.py` | Reads inside files — plain text, PDF text extraction, DOCX parsing |
| `assistant/prompts.py` | System prompts that force the LLM to explain simply, use analogies, avoid jargon |

### LLM Model Options (Already on Your System)

| Model | Size | Speed | Quality | Best For |
|---|---|---|---|---|
| Phi-3 Mini (3.8B) | ~2 GB | Fast | Good | Quick explanations |
| Llama 3.2 3B | ~2 GB | Fast | Good | Already cached on your system ✅ |
| Llama 3.1 8B | ~4.5 GB | Medium | Better | Detailed explanations |
| Mistral 7B | ~4 GB | Medium | Better | Technical accuracy |

---

## 🔮 PHASE 4: Compare with Cloud AI (Future)

> [!NOTE]
> **Not building now** — adds trust layer on top of Phase 3.

### What It Adds
A "Compare Answer" button that lets you cross-check the local AI's response with a cloud AI (ChatGPT, Gemini, Claude) for confidence.

### Two Modes

**Mode A — Simple Redirect (Free, No API Key):**
Opens the cloud AI's website with your question pre-filled. You compare manually.

**Mode B — Side-by-Side (Needs API Key):**
Calls the cloud AI's API and shows both answers next to each other, with an agreement indicator.

### Key Modules

| File | Purpose |
|---|---|
| `compare/platforms.py` | Builds redirect URLs for each platform (ChatGPT, Gemini, Claude, Perplexity) |
| `compare/side_by_side.py` | Optional: calls cloud API and returns comparison data |

---

## 📐 What We're Building in Phase 1 — File List

These are the exact files I'll create:

| # | File | Lines (est.) | Purpose |
|---|---|---|---|
| 1 | `requirements.txt` | 5 | Package list |
| 2 | `src/modules/core/config.py` | ~60 | Settings and defaults |
| 3 | `src/modules/core/utils.py` | ~80 | Helper functions |
| 4 | `src/modules/indexer/crawler.py` | ~90 | Directory walker |
| 5 | `src/modules/indexer/embedder.py` | ~70 | AI embedding generator |
| 6 | `src/modules/indexer/index_store.py` | ~120 | FAISS index manager |
| 7 | `src/modules/search/engine.py` | ~60 | Search query handler |
| 8 | `src/modules/search/ranker.py` | ~70 | Result re-ranker |
| 9 | `src/app.py` | ~140 | Flask server + routes |
| 10 | `src/templates/index.html` | ~200 | Main UI page |
| 11 | `src/static/style.css` | ~350 | Visual design |
| 12 | `src/static/app.js` | ~250 | Frontend interactions |
| 13 | `run.bat` | ~20 | One-click launcher |
| 14 | `guide.md` | ~80 | User guide |
| | **Total** | **~1,600** | |

---

## 📖 Glossary — Technical Terms in Plain English

If you come back to this plan days later, these definitions will help:

| Term | What It Actually Means |
|---|---|
| **Embedding** | A list of numbers that represents the "meaning" of a word or phrase. Similar meanings = similar numbers. |
| **FAISS** | A tool by Facebook that can search through millions of embeddings in milliseconds. Think of it as a super-fast library catalog organized by meaning. |
| **RAG** | Retrieval Augmented Generation — instead of the AI guessing from memory, it first looks up the actual document, then answers based on what it found. Like an open-book exam vs. a closed-book exam. |
| **Quantized LLM** | A large AI model that's been compressed to use less memory while keeping most of its intelligence. Like a ZIP file for AI brains. |
| **Vector** | Just a list of numbers. An embedding is a vector. When we say "vector search" we mean "searching by comparing lists of numbers." |
| **Flask** | A simple Python tool for creating web servers. It's what lets you open a page in your browser that talks to Python code running on your computer. |
| **Ollama** | An app that makes it easy to run AI models on your own computer without needing a PhD. Already installed on your machine. |
| **FAISS Index** | The actual file on disk that stores all the embeddings. Like a database but specifically designed for similarity search. |
| **Cosine Similarity** | A math formula that measures how similar two embeddings are. Score of 1.0 = identical meaning, 0.0 = completely unrelated. |
| **Debounce** | A technique where we wait a tiny bit (300ms) after you stop typing before searching. Prevents searching for "r", "re", "res", "resu", "resum", "resume" — just searches "resume". |

---

## ✅ Verification Plan

### After Building Phase 1

**Automated checks:**
1. Index a test folder with mixed file types
2. Search for exact names → verify they appear as #1 result
3. Search for semantic queries ("video editing" → find `.mp4` files, workflow JSONs)
4. Search for partial names → verify fuzzy matching works
5. Test the "Open File" and "Open Folder" buttons

**Manual checks:**
- Launch via `run.bat`, confirm browser opens automatically
- Verify the dark theme looks premium, not broken
- Test on different screen sizes (resize the browser window)
- Re-index after adding a new file, confirm it appears in search
- Confirm the filter buttons work (show only images, only docs, etc.)

---

## 🚀 Ready to Build

**Phase 1 scope:** Files 1–14 listed above (~1,600 lines of code)
**Estimated build time:** This session
**What you'll get:** A working search tool you can double-click to start, type a query, and find any file instantly

Everything is designed so Phases 2–4 plug in later without rewriting Phase 1.

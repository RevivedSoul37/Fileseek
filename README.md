# FileSeek

**A card catalog for your computer.** Search your files by *meaning*, not by name — 100% local, 100% private.

`13,489 files indexed` · `searches answer in 8–10 ms` · `0 bytes leave your machine`

![FileSeek — browse view](docs/assets/browse.png)

> “Think of it like a library card catalog, but instead of alphabetical order,
> it’s organized by *meaning*.” — from the original design doc

---

## The problem it solves

Windows Explorer only finds files whose **names** contain your words. But you don’t
remember names — you remember *intent*. You type `resume`; your file is called
`CV.pdf`. Explorer finds nothing. FileSeek finds it, because in its index,
“resume” and “CV” live next to each other.

Every file’s name, parent folder and type is converted into a 384-number
“meaning fingerprint” (an embedding) by a tiny on-device model
(`all-MiniLM-L6-v2`, ~22 MB), stored in a FAISS index, and searched in
milliseconds.

Real queries, real results, from the verification run on this machine:

| You type | The catalog pulls out | Why |
|---|---|---|
| `resume` | `Resume.pdf` — stamped 55% | exact + semantic agreement |
| `job application cv` | `Resume.pdf` | no shared words, same meaning |
| `cricket data` | `Fetching Cricket Player Data.md` | straight concept hit |
| `installer` | `ChatGPT Installer.exe` — 70% | literal + semantic |
| `python script` | `main.py` | type-aware semantic match |

![FileSeek — search with rubber-stamp match marks](docs/assets/search.png)

---

## The room

The interface is a night-shift card catalog, because that is exactly what the
index is:

- **Drawers** — category tabs (*Paper, Pictures, Film & sound, Code, Data,
  Bundles, Unfiled*) with live file counts. Pull one and the room refiles
  itself; no typing needed.
- **Cards** — results render as aged-paper index cards: red header rule,
  punched holes, path, size, age.
- **Stamps** — search results get a tilted rubber-stamp match mark
  (red = strong, brass = fair, faded = weak). Sensitive-looking filenames
  (`*token*`, `*password*`, `*.pem*`…) carry their own red mark.
- **Ledger** — the bottom bar keeps the count and last refile time, and the
  *Refile everything* button rebuilds the index.

`Ctrl K` jumps to the search slot from anywhere.

---

## Quick start

```
1. Double-click run.bat
2. First run builds the venv and installs dependencies (needs internet once)
3. It indexes Downloads, Documents and Desktop (~20 s per 10k files)
4. Your browser opens http://127.0.0.1:7860
```

That’s the whole ritual. Later runs load the saved index instantly.

### What your machine needs

| Requirement | Reality check |
|---|---|
| Python 3.10+ | built and verified on 3.11.15 |
| ~500 MB disk | index of 13.5k files ≈ 26 MB |
| GPU | **not required** — CPU FAISS answers in <10 ms at this scale |
| Internet | only for the one-time dependency install |

---

## Inside

```
walk folders ──▶ embed meaning ──▶ FAISS index ──▶ rank ──▶ cards
 crawler.py      embedder.py     index_store.py  ranker.py
```

| Module | Job |
|---|---|
| `src/modules/core/config.py` | scan roots, skip-list, port, model name |
| `src/modules/core/utils.py` | sizes, icons, categories, human time |
| `src/modules/indexer/crawler.py` | walks your folders, skips `node_modules`/`.git`/caches |
| `src/modules/indexer/embedder.py` | name + folder + type → 384-dim vector |
| `src/modules/indexer/index_store.py` | `IndexIDMap` over flat inner-product — incremental add/remove ready |
| `src/modules/search/engine.py` | query → embedding → nearest neighbours |
| `src/modules/search/ranker.py` | 60% semantic · 25% exact · 10% recency · 5% size |
| `src/app.py` | Flask server: `/api/search`, `/api/browse`, `/api/index`, open file/folder |
| `src/static/` + `src/templates/` | the card-catalog UI |

### A bug the design doc predicted

The plan warned: *“searching ‘Resume’ might show `resume_background.png` above
your actual `Resume.pdf`.”* Testing proved it — two long test filenames beat the
real resume. The fix made the exact-match weight **coverage-based** (how much
of the filename your query covers), and `Resume.pdf` took #1. The warning was
right; the ranker now is too.

---

## Verification

`scripts/verify_build.py` runs the full suite — **26/26 checks stamped**:

| Check | Stamp |
|---|---|
| Crawl 13,461 files in 0.8 s | PASSED |
| Embeddings (13461 × 384), L2-normalized | PASSED |
| Index build → save → reload from disk | PASSED |
| 5 semantic searches, 8–10 ms each | PASSED |
| Incremental add / remove (Phase-2 ready) | PASSED |
| Category filters return only their drawer | PASSED |

A human-readable **field test protocol** was authored alongside this build —
a paper protocol sheet where clicking a row slams a red *PASSED* stamp down
and a live tally counts your progress.

![Field test protocol](docs/assets/testplan.png)

---

## Roadmap

| Phase | Status | Adds |
|---|---|---|
| 1 · Semantic search + card catalog UI | **done** | this repo |
| 2 · Live watcher | next | `watchdog` keeps the index current; activity feed |
| 3 · Plain-language assistant | planned | local LLM (Ollama) explains any file in your words |
| 4 · Compare with cloud AI | planned | opt-in second opinion from ChatGPT/Gemini/Claude |

The `watcher/`, `assistant/` and `compare/` packages already exist as empty
sockets so later phases plug in without rewriting Phase 1.

---

## Privacy

Everything runs on your machine. File names are embedded locally by a 22 MB
model; nothing is uploaded, phoned home, or telemetered. Phase 4’s cloud
comparison will be explicitly opt-in and clearly labeled.

---

## Design notes

The UI was designed under the [`frontend-design`](docs/skills/frontend-design/SKILL.md)
skill as **“the night-shift card catalog”**: lacquer green `#0E1915`, aged paper
`#F3ECD9`, brass `#C9A227`, stamp red `#B3402E`; set in Fraunces, Karla and
IBM Plex Mono; signature element is the rubber-stamp match mark.

```
docs/            skill, screenshots
src/modules/     backend
src/static|templates/  frontend
data/            your index (git-ignored, rebuilt on launch)
```

*FileSeek — find what you forgot you had.*
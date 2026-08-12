# FileSeek — Personal Testing Plan

> Built from YOUR actual index (13,461 files: Desktop 11,861 · Documents 1,052 · Downloads 548).
> Every expected answer below is a real file that exists in your index, so you can verify FileSeek is telling the truth.

**How to run:** launch `run.bat`, open http://127.0.0.1:7860, then work top to bottom. Tick [x] as you go.

---

## Tier 0 — Browse Mode (no typing)

- [ ] Page loads and immediately shows your newest files with a "Browsing all categories" header
- [ ] Click **🎬 Media** — expect 254 files, top results should be sound effects like `freesound_community-wowowowowowowow-103214.mp3`
- [ ] Click **📦 Archives** — expect 45 files, biggest should be `ComfyUI_windows_portable_nvidia.7z` (1,995 MB)
- [ ] Click **📊 Data** — expect ~5,617 files (your biggest category — mostly JSON datasets)
- [ ] Clear the search box → browse view returns

## Tier 1 — Exact Name Recall

| Type this | Expected #1 result | Tick |
|---|---|---|
| `Resume.pdf` | `Resume.pdf` in `Downloads\04-Documents` (~85%+ match) | [ ] |
| `implementation_plan.md` | This planning doc in `Desktop\FileSeek` | [ ] |
| `ORGANIZE_LOG.txt` | The Downloads cleanup log | [ ] |
| `ChatGPT Installer.exe` | The installer in Downloads | [ ] |

## Tier 2 — Semantic Search (the interesting part)

These queries use words that do NOT appear in the filenames:

| Type this | Should surface | Why it's a true semantic hit | Tick |
|---|---|---|---|
| `job application cv` | `Resume.pdf` | "job application" ≈ "resume" in meaning-space | [ ] |
| `3d modeling sculpture` | `blender-5.1.2-windows-x64.msi` | Blender = 3D tool, never named in file | [ ] |
| `ai image generation models` | `ComfyUI_windows_portable_nvidia.7z` and/or `ZIT loras.zip` | LoRAs + ComfyUI = image-gen ecosystem | [ ] |
| `voice dictation speech to text` | `Wispr Flow Setup-v1.6.7.exe` | Wispr Flow is a dictation app | [ ] |
| `container virtualization docker` | `Docker Desktop Installer.exe` | container → Docker | [ ] |
| `cricket data` | `Fetching Cricket Player Data.md` | exact concept match | [ ] |

## Tier 3 — Find Things You Forgot You Had

- [ ] Type `screen recording` → should surface `Desktop 2026.08.09 - 13.18.08.01.mp4` (220 MB recording)
- [ ] Type `game design` → should surface `Aether_Bound_Game_Design_v2.docx`
- [ ] Type `sun space nasa` → should surface `sun-sdo-active-304.jpg` (a Solar Dynamics Observatory image!)
- [ ] Type `agent memory` → should surface the `CreativeOS Agent Memory structure layered update` docs
- [ ] Type `story bible worldbuilding` → see what lore files you've accumulated

## Tier 4 — Sensitive File Audit (34 flagged)

Your index tagged **34 sensitive-named files**. Verify the 🔒 badge appears:

- [ ] Type `token` → files like `session-tokens.ts`, `token-registry.ts` show 🔒 sensitive badges
- [ ] Type `password` → `password.go` shows the badge
- [ ] Decide: are any of these REAL secrets (not just code about tokens)? If yes, consider moving them outside the indexed folders or out of plain-text filenames.

## Tier 5 — Actions & Edge Cases

- [ ] **Open File** on `Resume.pdf` → opens in your PDF viewer
- [ ] **Open Folder** on any result → Explorer opens with the file highlighted
- [ ] Type `zzzzqqqq` → friendly "no matches" empty state (not a crash)
- [ ] Type one character `a` → debounced, no lag
- [ ] `Ctrl+K` anywhere → cursor jumps to search bar
- [ ] **🔄 Re-index** → status bar shows live progress, search keeps working from the old index until rebuild completes

## Tier 6 — Scale Check

- [ ] Status pill reads **"13,461 files indexed"**
- [ ] Any search returns in **< 50ms** (check browser DevTools → Network tab timing)

---

## Expected cleanup discoveries (from your earlier Downloads audit)

While browsing, you'll likely re-spot these worth acting on:
- **~700 MB duplicate installers**: `Wispr Flow Setup-v1.6.7.exe` + `v1.5.1095` (333 MB + 329 MB)
- **2 GB ComfyUI archive** + **1.6 GB ZIT loras.zip** — confirm they're unpacked, then archivable
- **`Docker Desktop Installer.exe` (602 MB)** — one-time installer, safe to delete post-install

## Known limitations (Phase 1 scope)

- No live refresh yet — new files won't appear until you hit Re-index (Phase 2 watcher fixes this)
- Browse mode shows 60 most-recent per category (search mode finds everything)
- `data` category is dominated by numeric-named `.json` dataset files — their names carry little meaning, so semantic search on them is weaker by nature
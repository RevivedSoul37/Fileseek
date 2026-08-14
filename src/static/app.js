const searchInput = document.getElementById('search-input');
const resultsEl = document.getElementById('results');
const emptyState = document.getElementById('empty-state');
const statusPill = document.getElementById('status-pill');
const indexInfo = document.getElementById('index-info');
const progressText = document.getElementById('progress-text');
const reindexBtn = document.getElementById('reindex-btn');
const toastEl = document.getElementById('toast');
const filterButtons = document.querySelectorAll('.filter-btn');
const activityBtn = document.getElementById('activity-btn');
const activityDrawer = document.getElementById('activity-drawer');
const activityList = document.getElementById('activity-list');
const activityClose = document.getElementById('activity-close');

let currentCategory = 'all';
let currentScope = 'files';
let contentIndexed = false;
const CAT_LABELS = {
    all: 'everything', document: 'paper', image: 'pictures', media: 'film & sound',
    code: 'code', data: 'data', archive: 'bundles', other: 'unfiled'
};
let currentIndexed = false;
let debounceTimer = null;
let statusTimer = null;
let baseCounts = {};
let lastSearchCounts = null;
let lastSearchTotal = 0;
let askAvailable = false;

function debounce(fn, ms) {
    return (...args) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => fn(...args), ms);
    };
}

function toast(message) {
    toastEl.textContent = message;
    toastEl.classList.add('show');
    setTimeout(() => toastEl.classList.remove('show'), 2400);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : text;
    return div.innerHTML;
}

function matchClass(percent) {
    if (percent >= 55) return 'match-high';
    if (percent >= 35) return 'match-mid';
    return 'match-low';
}

function applyTabCounts() {
    const searching = searchInput.value.trim().length > 0 && lastSearchCounts;
    document.querySelectorAll('.tab-count').forEach(el => {
        const cat = el.dataset.cat;
        let n;
        if (searching) {
            n = cat === 'all'
                ? Object.values(lastSearchCounts).reduce((a, b) => a + b, 0)
                : (lastSearchCounts[cat] || 0);
            el.textContent = n.toLocaleString();
            el.classList.toggle('search-count', true);
        } else {
            n = cat === 'all'
                ? Object.values(baseCounts).reduce((a, b) => a + b, 0)
                : (baseCounts[cat] || 0);
            el.textContent = n ? n.toLocaleString() : '';
            el.classList.toggle('search-count', false);
        }
    });
}

function setPill(text, cls) {
    statusPill.textContent = text;
    statusPill.className = 'status-pill ' + cls;
}

function timeAgo(ts) {
    const seconds = Math.max(0, Date.now() / 1000 - ts);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
    return `${Math.floor(seconds / 86400)} days ago`;
}

function resultCard(r) {
    const sensitiveBadge = r.sensitive
        ? `<span class="sensitive-badge" title="Filename matches a sensitive pattern">` + '🔒 sensitive' + `</span>`
        : '';
    const matchBadge = r.match_percent != null
        ? `<span class="match-badge ${matchClass(r.match_percent)}">${r.match_percent}%</span>`
        : '';
    const semanticInfo = r.semantic_percent != null ? ' · semantic ' + r.semantic_percent + '%' : '';
    const diffLine = diffSummaryLine(r);
    const snippetLine = r.snippet
        ? `<div class="result-snippet" title="${escapeHtml(r.snippet)}">📄 ${escapeHtml(r.snippet)}</div>`
        : '';
    return `
    <div class="result-card">
        <div class="result-icon">${r.icon}</div>
        <div class="result-body">
            <div class="result-name-row">
                <span class="result-name" title="${escapeHtml(r.name)}">${escapeHtml(r.name)}</span>
                ${sensitiveBadge}
            </div>
            <div class="result-path" title="${escapeHtml(r.path)}">${escapeHtml(r.path)}</div>
            <div class="result-meta">${r.parent_folder ? escapeHtml(r.parent_folder) + ' · ' : ''}${r.size_display} · ${r.modified_display}${semanticInfo}</div>
            ${snippetLine}
            ${diffLine}
        </div>
        <div class="result-actions">
            ${matchBadge}
            <button class="icon-btn" data-action="file" data-path="${escapeHtml(r.path)}">Open File</button>
            <button class="icon-btn" data-action="folder" data-path="${escapeHtml(r.path)}">Open Folder</button>
            <button class="icon-btn ask-btn" data-action="ask" data-path="${escapeHtml(r.path)}" data-name="${escapeHtml(r.name)}" title="Ask a local AI what this file is">Ask</button>
        </div>
        <div class="ask-panel" hidden></div>
    </div>`;
}

function diffSummaryLine(r) {
    if (!r.last_diff_summary && !r.last_diff_size_delta) return '';
    const parts = [];
    if (r.last_diff_summary) parts.push(r.last_diff_summary);
    if (r.last_diff_size_delta) {
        parts.push((r.last_diff_size_delta > 0 ? '+' : '') + r.last_diff_size_delta.toLocaleString() + ' B');
    }
    return `<div class="result-diff" title="Last change summary">✏️ ${escapeHtml(parts.join(' · '))}</div>`;
}

async function browse(category) {
    if (!currentIndexed) return;
    try {
        const res = await fetch('/api/browse?category=' + (category || currentCategory) + '&limit=60');
        const data = await res.json();
        const catLabel = (category && category !== 'all') ? CAT_LABELS[category] || category : 'everything';
        if (!data.results || data.results.length === 0) {
            resultsEl.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📭</div>
                    <h2>No files in this category</h2>
                    <p>Try another filter, or hit Re-index if you just added files.</p>
                </div>`;
            return;
        }
        resultsEl.innerHTML =
            `<div class="browse-header">🗂️ Browsing <strong>${escapeHtml(catLabel)}</strong> — ${data.total.toLocaleString()} files indexed · showing ${data.results.length} most recent</div>` +
            data.results.map(r => resultCard(r)).join('');
    } catch (e) {
        toast('Browse failed — is the server running?');
    }
}

const ACTIVITY_ICONS = {
    created: '📄',
    modified: '✏️',
    deleted: '🗑️',
    moved: '➡️',
    moved_dir: '📁➡️'
};

function activityRowHtml(entry) {
    const icon = ACTIVITY_ICONS[entry.kind] || '•';
    const when = timeAgo(entry.ts);
    let detail = escapeHtml(entry.name || '');
    if (entry.kind === 'moved' || entry.kind === 'moved_dir') {
        detail = escapeHtml((entry.from || '?') + ' → ' + (entry.to || entry.name || '?'));
    }
    const diff = entry.diff_summary
        ? `<span class="activity-diff">✏️ ${escapeHtml(entry.diff_summary)}</span>`
        : '';
    return `
        <div class="activity-row">
            <span class="activity-icon">${icon}</span>
            <div class="activity-body">
                <div class="activity-name" title="${escapeHtml(entry.name || '')}">${detail}</div>
                ${diff}
            </div>
            <span class="activity-when">${when}</span>
        </div>`;
}

async function loadActivity() {
    try {
        const res = await fetch('/api/activity?limit=60');
        const data = await res.json();
        if (!data.ok) return;
        if (!data.entries || data.entries.length === 0) {
            activityList.innerHTML = `<div class="activity-empty">Nothing logged yet — make a change in a watched folder and it lands here.</div>`;
            return;
        }
        activityList.innerHTML = data.entries.map(activityRowHtml).join('');
    } catch (e) {
        activityList.innerHTML = `<div class="activity-empty">Could not load activity — is the server running?</div>`;
    }
}

function toggleActivityDrawer(forceOpen) {
    const opening = forceOpen !== undefined ? forceOpen : activityDrawer.hidden;
    activityDrawer.hidden = !opening;
    if (opening) {
        loadActivity();
        activityBtn.classList.add('active');
    } else {
        activityBtn.classList.remove('active');
    }
}

activityBtn.addEventListener('click', () => toggleActivityDrawer());
activityClose.addEventListener('click', () => toggleActivityDrawer(false));

/* ── Settings modal — edit which folders get scanned ── */
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const settingsClose = document.getElementById('settings-close');
const settingsList = document.getElementById('settings-list');
const settingsAddForm = document.getElementById('settings-add-form');
const settingsAddInput = document.getElementById('settings-add-input');
const settingsError = document.getElementById('settings-error');
const settingsSave = document.getElementById('settings-save');
const settingsContentToggle = document.getElementById('settings-content-toggle');
const scopeToggle = document.getElementById('scope-toggle');
const scopeButtons = document.querySelectorAll('.scope-btn');
let pendingDirs = [];

scopeButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        scopeButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentScope = btn.dataset.scope;
        if (searchInput.value.trim()) runSearch();
    });
});

function renderSettingsList() {
    settingsList.innerHTML = pendingDirs.map((dir, i) => `
        <div class="settings-row">
            <span class="settings-dir" title="${escapeHtml(dir)}">📁 ${escapeHtml(dir)}</span>
            <button class="ask-close settings-remove" data-index="${i}" title="Remove this folder">✕</button>
        </div>`).join('') || `<div class="settings-empty">no folders yet — add at least one to save</div>`;
}

function setSettingsError(message) {
    if (!message) {
        settingsError.hidden = true;
        settingsError.textContent = '';
        return;
    }
    settingsError.hidden = false;
    settingsError.textContent = '❌ ' + message;
}

async function openSettings() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        pendingDirs = (data.scan_dirs || []).slice();
        settingsContentToggle.checked = !!data.content_index_enabled;
        contentIndexed = data.content_index && data.content_index.chunks > 0;
        scopeToggle.hidden = !contentIndexed;
        renderSettingsList();
        setSettingsError('');
        settingsModal.hidden = false;
    } catch (e) {
        toast('Could not load settings — is the server running?');
    }
}

function closeSettings() {
    settingsModal.hidden = true;
}

settingsAddForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const dir = settingsAddInput.value.trim();
    if (!dir) return;
    if (pendingDirs.includes(dir)) {
        setSettingsError('That folder is already in the list');
        return;
    }
    pendingDirs.push(dir);
    settingsAddInput.value = '';
    setSettingsError('');
    renderSettingsList();
});

settingsList.addEventListener('click', (event) => {
    const removeBtn = event.target.closest('.settings-remove');
    if (!removeBtn) return;
    pendingDirs.splice(parseInt(removeBtn.dataset.index, 10), 1);
    setSettingsError('');
    renderSettingsList();
});

settingsSave.addEventListener('click', async () => {
    setSettingsError('');
    settingsSave.disabled = true;
    try {
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scan_dirs: pendingDirs, content_index_enabled: settingsContentToggle.checked })
        });
        const data = await res.json();
        if (!data.ok) {
            setSettingsError(data.error || 'Could not save settings');
            return;
        }
        toast('Saved — re-index started, watcher will resume when done');
        closeSettings();
        refreshStatus();
    } catch (e) {
        setSettingsError('Server did not respond — is FileSeek still running?');
    } finally {
        settingsSave.disabled = false;
    }
});

settingsModal.addEventListener('click', (event) => {
    if (event.target === settingsModal) closeSettings();
});
settingsBtn.addEventListener('click', openSettings);
settingsClose.addEventListener('click', closeSettings);

async function refreshStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const wasIndexed = currentIndexed;
        currentIndexed = data.indexed;
        if (data.indexed) {
            setPill(data.file_count.toLocaleString() + ' files indexed', 'ready');
            indexInfo.textContent = 'Index: ' + data.file_count.toLocaleString() + ' files';
        } else if (data.indexing) {
            setPill('indexing…', 'loading');
            indexInfo.textContent = 'Index: building…';
        } else {
            setPill('no index yet', 'loading');
            indexInfo.textContent = 'Index: empty';
        }
        if (data.watching) {
            setPill(statusPill.textContent + ' · watching live', 'ready');
        }
        askAvailable = !!data.ask_available;
        if (askAvailable) {
            setPill(statusPill.textContent + ' · ask ready', 'ready');
        }
        progressText.textContent = data.progress && data.indexing ? data.progress : '';
        reindexBtn.disabled = !!data.indexing;
        reindexBtn.textContent = data.indexing ? '⏳ Indexing…' : '🔄 Refile everything';
        if (data.indexed && data.last_indexed) {
            indexInfo.textContent += ' · updated ' + timeAgo(data.last_indexed);
        }
        if (data.categories) {
            baseCounts = data.categories;
            applyTabCounts();
        }
        if (!wasIndexed && data.indexed && !searchInput.value.trim()) {
            browse(currentCategory);
        }
    } catch (e) {
        setPill('server offline', 'error');
        return;
    }
    if (!activityDrawer.hidden) loadActivity();
}

function showEmptyState() {
    resultsEl.innerHTML = '';
    resultsEl.appendChild(emptyState);
}

function renderResults(results, query, total, showAll) {
    if (!results || results.length === 0) {
        resultsEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <h2>No matches for “${escapeHtml(query)}”</h2>
                <p>Try different words or a broader concept.</p>
            </div>`;
        return;
    }
    const shown = results.length;
    const hasMore = total != null && total > shown;
    const shownTotal = total != null ? total : shown;
    const totalLine = hasMore
        ? `${total.toLocaleString()} matches — showing top ${shown.toLocaleString()}`
        : `${shownTotal.toLocaleString()} match${shownTotal === 1 ? '' : 'es'}`;
    const showAllBtn = hasMore && !showAll
        ? `<button class="show-all-btn" data-action="show-all" data-limit="${total}">Show all ${total.toLocaleString()}</button>`
        : '';
    resultsEl.innerHTML =
        `<div class="browse-header">🔎 <strong>${escapeHtml(query)}</strong> — ${totalLine}${showAllBtn}</div>` +
        results.map(r => resultCard(r)).join('');
}

async function runSearch(limit) {
    const query = searchInput.value.trim();
    if (!query) {
        browse(currentCategory);
        return;
    }
    if (!currentIndexed) {
        resultsEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">⏳</div>
                <h2>Building your index…</h2>
                <p>FileSeek is scanning and embedding your files. Search unlocks in a few seconds.</p>
            </div>`;
        return;
    }
    const showAll = limit != null;
    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, category: currentCategory, limit: limit || undefined, scope: currentScope })
        });
        const data = await res.json();
        contentIndexed = !!data.content_indexed;
        scopeToggle.hidden = !contentIndexed;
        lastSearchCounts = data.category_counts || {};
        lastSearchTotal = data.total != null ? data.total : data.results.length;
        applyTabCounts();
        renderResults(data.results, query, data.total, showAll);
    } catch (e) {
        toast('Search failed — is the server running?');
    }
}

const debouncedSearch = debounce(runSearch, 300);

searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim();
    if (!q) {
        lastSearchCounts = null;
        lastSearchTotal = 0;
        applyTabCounts();
        browse(currentCategory);
        return;
    }
    debouncedSearch();
});

function askQuestionHtml() {
    return `
        <button class="ask-close" data-action="close-ask" title="Close this panel">✕</button>
        <form class="ask-question-form">
            <input class="ask-question-input" type="text" placeholder="ask in your own words… (empty = default question)" maxlength="500" autocomplete="off">
            <button class="icon-btn ask-btn" type="submit">📮 Ask</button>
        </form>`;
}

function askLoadingHtml() {
    return `<div class="ask-loading">🔎 Asking the local model to read this file… <span class="ask-loading-sub">first ask after a pause can take a few seconds</span></div>`;
}

function askErrorHtml(message) {
    return `<div class="ask-error">❌ ${escapeHtml(message || 'The ask did not come back — try again')}</div>`;
}

function askAnswerHtml(data, path) {
    const sensitive = data.sensitive
        ? `<div class="ask-sensitive">marked sensitive — reviewed locally only, nothing leaves this machine</div>`
        : '';
    const truncatedNote = data.truncated ? ' · file was truncated' : '';
    const seconds = (data.elapsed_ms / 1000).toFixed(1);
    return `
        <button class="ask-close" data-action="close-ask" title="Close this answer">✕</button>
        ${sensitive}
        <div class="ask-answer">${escapeHtml(data.answer)}</div>
        <div class="ask-footer">stamped by ${escapeHtml(data.model)} · ${seconds}s${truncatedNote} · 100% local
            <button class="icon-btn ask-more-btn" data-action="ask-more" title="Keep talking to the model about this file">💬 Ask more</button>
            <button class="icon-btn ask-more-btn" data-action="full-chat" data-path="${escapeHtml(path)}" title="Open the full conversation page">⛶ Full chat</button>
            <button class="icon-btn ask-more-btn compare-btn" data-action="compare" data-path="${escapeHtml(path)}" title="Ask a cloud AI about this file's name, type and size — never its content">☁ Compare</button>
        </div>`;
}

async function submitAsk(panel, path, question) {
    panel.hidden = false;
    panel.dataset.state = 'loading';
    panel.innerHTML = askLoadingHtml();
    try {
        const res = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, question: question || '' })
        });
        const data = await res.json();
        if (!data.ok) {
            panel.innerHTML = askErrorHtml(data.error);
            panel.dataset.state = 'error';
            return;
        }
        panel.dataset.askQuestion = data.question || '';
        panel.dataset.askPath = path;
        panel.innerHTML = askAnswerHtml(data, path);
        panel.dataset.state = 'done';
    } catch (e) {
        panel.innerHTML = askErrorHtml('Server did not respond — is FileSeek still running?');
        panel.dataset.state = 'error';
    }
}

function askAboutFile(btn) {
    const card = btn.closest('.result-card');
    const panel = card ? card.querySelector('.ask-panel') : null;
    if (!panel) return;
    if (!panel.hidden && panel.dataset.state === 'loading') return;
    if (!panel.hidden && panel.dataset.state === 'done') {
        panel.hidden = true;
        panel.dataset.state = '';
        return;
    }
    if (!panel.hidden && panel.dataset.state === 'question') {
        const input = panel.querySelector('.ask-question-input');
        if (input) input.focus();
        return;
    }
    panel.hidden = false;
    panel.dataset.state = 'question';
    panel.innerHTML = askQuestionHtml();
    const input = panel.querySelector('.ask-question-input');
    if (input) input.focus();
}

function chatBubbleHtml(turn) {
    return `<div class="ask-msg ask-msg-${turn.role}">${escapeHtml(turn.content)}</div>`;
}

function chatMetaHtml(meta) {
    const parts = ['stamped by ' + escapeHtml(meta.model)];
    if (meta.sensitive) parts.push('marked sensitive — local only');
    if (meta.context_files) parts.push('folder clues: ' + meta.context_files + ' sibling files');
    parts.push('100% local');
    return `<div class="ask-footer">${parts.join(' · ')}</div>`;
}

function renderChat(panel) {
    const messages = (panel._history || []).map(chatBubbleHtml).join('');
    panel.innerHTML = `
        <button class="ask-close" data-action="close-ask" title="Close this conversation">✕</button>
        <div class="ask-chat">
            <div class="ask-chat-log">${messages}</div>
            <form class="ask-chat-form">
                <input class="ask-chat-input" type="text" placeholder="Ask more about this file…" maxlength="1000" autocomplete="off">
                <button class="icon-btn ask-chat-send" type="submit">Send</button>
            </form>
            ${chatMetaHtml(panel._chatMeta || { model: 'local model' })}
            <div class="ask-chat-actions">
                <button class="icon-btn compare-btn" data-action="compare" data-path="${escapeHtml(panel.dataset.askPath || '')}" title="Ask a cloud AI about this file's name, type and size — never its content">☁ Compare</button>
                <button class="icon-btn" data-action="full-chat" data-path="${escapeHtml(panel.dataset.askPath || '')}" title="Open the full conversation page">⛶ Full chat</button>
            </div>
        </div>`;
    const input = panel.querySelector('.ask-chat-input');
    if (input) input.focus();
}

function startChat(panel, btn) {
    const answerEl = panel.querySelector('.ask-answer');
    const answer = answerEl ? answerEl.textContent : '';
    const question = panel.dataset.askQuestion || 'What is this file and what does it do?';
    panel._history = [
        { role: 'user', content: question },
        { role: 'assistant', content: answer }
    ];
    panel._chatMeta = panel._chatMeta || { model: 'local model', sensitive: !!panel.querySelector('.ask-sensitive') };
    panel.hidden = false;
    panel.dataset.state = 'chat';
    renderChat(panel);
}

async function sendChat(panel, question) {
    const input = panel.querySelector('.ask-chat-input');
    const sendBtn = panel.querySelector('.ask-chat-send');
    const log = panel.querySelector('.ask-chat-log');
    panel._history.push({ role: 'user', content: question });
    if (input) input.disabled = true;
    if (sendBtn) sendBtn.disabled = true;
    if (log) log.insertAdjacentHTML('beforeend',
        chatBubbleHtml({ role: 'user', content: question }) +
        `<div class="ask-chat-typing">the model is reading the folder clues…</div>`);
    try {
        const history = panel._history.slice(0, -1);
        const res = await fetch('/api/ask-more', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: panel.dataset.askPath, history, question })
        });
        const data = await res.json();
        const typing = panel.querySelector('.ask-chat-typing');
        if (typing) typing.remove();
        if (!data.ok) {
            panel._history.pop();
            if (log) log.insertAdjacentHTML('beforeend', askErrorHtml(data.error));
        } else {
            panel._history.push({ role: 'assistant', content: data.answer });
            panel._chatMeta = {
                model: data.model,
                sensitive: data.sensitive,
                context_files: data.context_files
            };
            renderChat(panel);
        }
    } catch (e) {
        panel._history.pop();
        const typing = panel.querySelector('.ask-chat-typing');
        if (typing) typing.remove();
        const log2 = panel.querySelector('.ask-chat-log');
        if (log2) log2.insertAdjacentHTML('beforeend', askErrorHtml('Server did not respond — is FileSeek still running?'));
    } finally {
        const input2 = panel.querySelector('.ask-chat-input');
        const send2 = panel.querySelector('.ask-chat-send');
        if (input2) input2.disabled = false;
        if (send2) send2.disabled = false;
    }
}

async function compareWithCloud(btn) {
    const path = btn.dataset.path;
    if (!path) return;
    btn.disabled = true;
    try {
        const res = await fetch('/api/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        const data = await res.json();
        if (!data.ok) {
            toast(data.error || 'Compare did not come back — try again');
            return;
        }
        if (data.sensitive && !window.confirm('This file is marked sensitive.\nOnly its name, type and size would leave this machine — never its content.\nOpen the cloud AIs anyway?')) {
            return;
        }
        data.links.forEach(link => window.open(link.url, '_blank'));
        toast('Opened ' + data.links.length + ' cloud AIs — name/type/size only, content stays local');
    } catch (e) {
        toast('Compare failed — is FileSeek still running?');
    } finally {
        btn.disabled = false;
    }
}

resultsEl.addEventListener('click', async (event) => {
    const btn = event.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    if (action === 'show-all') {
        runSearch(parseInt(btn.dataset.limit, 10) || undefined);
        return;
    }
    if (action === 'compare') {
        compareWithCloud(btn);
        return;
    }
    if (action === 'ask') {
        if (!askAvailable) {
            toast('Ask is offline — start Ollama (`ollama serve`) to enable it');
        }
        askAboutFile(btn);
        return;
    }
    if (action === 'ask-more') {
        const card = btn.closest('.result-card');
        const panel = card ? card.querySelector('.ask-panel') : null;
        if (!panel) return;
        if (panel.dataset.state === 'chat') {
            const input = panel.querySelector('.ask-chat-input');
            if (input) input.focus();
            return;
        }
        if (panel.dataset.state !== 'done' || panel.hidden) return;
        startChat(panel);
        return;
    }
    if (action === 'close-ask') {
        const card = btn.closest('.result-card');
        const panel = card ? card.querySelector('.ask-panel') : null;
        if (!panel) return;
        panel.hidden = true;
        panel.dataset.state = '';
        panel._history = null;
        return;
    }
    if (action === 'full-chat') {
        window.open('/chat?path=' + encodeURIComponent(btn.dataset.path), '_blank');
        return;
    }
    const path = btn.dataset.path;
    const endpoint = action === 'file' ? '/api/open/file' : '/api/open/folder';
    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        const data = await res.json();
        if (!data.ok) toast(data.error || 'Could not open');
    } catch (e) {
        toast('Could not open path');
    }
});

resultsEl.addEventListener('submit', (event) => {
    const askForm = event.target.closest('.ask-question-form');
    if (askForm) {
        event.preventDefault();
        const panel = askForm.closest('.ask-panel');
        const card = askForm.closest('.result-card');
        const input = askForm.querySelector('.ask-question-input');
        const askBtn = card ? card.querySelector('.ask-btn[data-action="ask"]') : null;
        if (!panel || !askBtn) return;
        submitAsk(panel, askBtn.dataset.path, (input ? input.value : '').trim());
        return;
    }
    const form = event.target.closest('.ask-chat-form');
    if (!form) return;
    event.preventDefault();
    const panel = form.closest('.ask-panel');
    const input = form.querySelector('.ask-chat-input');
    const question = (input ? input.value : '').trim();
    if (!panel || !question) return;
    input.value = '';
    sendChat(panel, question);
});

filterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        filterButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentCategory = btn.dataset.category;
        if (searchInput.value.trim()) {
            runSearch();
        } else {
            browse(currentCategory);
        }
    });
});

reindexBtn.addEventListener('click', async () => {
    try {
        const res = await fetch('/api/index', { method: 'POST' });
        const data = await res.json();
        toast(data.started ? 'Re-index started' : 'Already indexing');
        refreshStatus();
    } catch (e) {
        toast('Could not start re-index');
    }
});

document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchInput.focus();
        searchInput.select();
    }
    if (event.key === 'Escape') searchInput.blur();
});

refreshStatus();
browse(currentCategory);
statusTimer = setInterval(refreshStatus, 4000);
searchInput.focus();
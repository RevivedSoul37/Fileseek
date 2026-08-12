const searchInput = document.getElementById('search-input');
const resultsEl = document.getElementById('results');
const emptyState = document.getElementById('empty-state');
const statusPill = document.getElementById('status-pill');
const indexInfo = document.getElementById('index-info');
const progressText = document.getElementById('progress-text');
const reindexBtn = document.getElementById('reindex-btn');
const toastEl = document.getElementById('toast');
const filterButtons = document.querySelectorAll('.filter-btn');

let currentCategory = 'all';
const CAT_LABELS = {
    all: 'everything', document: 'paper', image: 'pictures', media: 'film & sound',
    code: 'code', data: 'data', archive: 'bundles', other: 'unfiled'
};
let currentIndexed = false;
let debounceTimer = null;
let statusTimer = null;

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
        </div>
        <div class="result-actions">
            ${matchBadge}
            <button class="icon-btn" data-action="file" data-path="${escapeHtml(r.path)}">Open File</button>
            <button class="icon-btn" data-action="folder" data-path="${escapeHtml(r.path)}">Open Folder</button>
        </div>
    </div>`;
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
        progressText.textContent = data.progress && data.indexing ? data.progress : '';
        reindexBtn.disabled = !!data.indexing;
        reindexBtn.textContent = data.indexing ? '⏳ Indexing…' : '🔄 Re-index';
        if (data.indexed && data.last_indexed) {
            indexInfo.textContent += ' · updated ' + timeAgo(data.last_indexed);
        }
        if (data.categories) {
            document.querySelectorAll('.tab-count').forEach(el => {
                const n = data.categories[el.dataset.cat];
                el.textContent = n ? n.toLocaleString() : '';
            });
        }
        if (!wasIndexed && data.indexed && !searchInput.value.trim()) {
            browse(currentCategory);
        }
    } catch (e) {
        setPill('server offline', 'error');
    }
}

function showEmptyState() {
    resultsEl.innerHTML = '';
    resultsEl.appendChild(emptyState);
}

function renderResults(results, query) {
    if (!results || results.length === 0) {
        resultsEl.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <h2>No matches for "${escapeHtml(query)}"</h2>
                <p>Try different words or a broader concept.</p>
            </div>`;
        return;
    }
    resultsEl.innerHTML = results.map(r => resultCard(r)).join('');
}

async function runSearch() {
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
    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, category: currentCategory })
        });
        const data = await res.json();
        renderResults(data.results, query);
    } catch (e) {
        toast('Search failed — is the server running?');
    }
}

const debouncedSearch = debounce(runSearch, 300);

searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim();
    if (!q) {
        browse(currentCategory);
        return;
    }
    debouncedSearch();
});

resultsEl.addEventListener('click', async (event) => {
    const btn = event.target.closest('[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
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
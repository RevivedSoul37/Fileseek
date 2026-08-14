const params = new URLSearchParams(window.location.search);
const filePath = params.get('path') || '';

const logEl = document.getElementById('chat-log');
const formEl = document.getElementById('chat-form');
const inputEl = document.getElementById('chat-input');
const sendEl = document.getElementById('chat-send');
const nameEl = document.getElementById('chat-file-name');
const pathEl = document.getElementById('chat-file-path');
const iconEl = document.getElementById('chat-file-icon');
const sensitiveEl = document.getElementById('chat-sensitive');
const stampEl = document.getElementById('chat-stamp');
const compareBtnEl = document.getElementById('chat-compare');

let history = [];
let busy = false;

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : text;
    return div.innerHTML;
}

function bubble(role, text) {
    const el = document.createElement('div');
    el.className = 'chat-bubble chat-' + role;
    el.textContent = text;
    logEl.appendChild(el);
    logEl.scrollTop = logEl.scrollHeight;
    return el;
}

function typingBubble() {
    const el = document.createElement('div');
    el.className = 'chat-bubble chat-assistant chat-typing';
    el.textContent = 'reading the file and its folder clues…';
    logEl.appendChild(el);
    logEl.scrollTop = logEl.scrollHeight;
    return el;
}

function setBusy(on) {
    busy = on;
    inputEl.disabled = on;
    sendEl.disabled = on;
    if (!on) inputEl.focus();
}

async function sendQuestion(question) {
    if (busy || !question) return;
    setBusy(true);
    bubble('user', question);
    const typing = typingBubble();
    history.push({ role: 'user', content: question });
    try {
        const res = await fetch('/api/ask-more', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filePath, history: history.slice(0, -1), question })
        });
        const data = await res.json();
        typing.remove();
        if (!data.ok) {
            history.pop();
            bubble('assistant', '❌ ' + (data.error || 'The answer did not come back — try again.'));
        } else {
            history.push({ role: 'assistant', content: data.answer });
            bubble('assistant', data.answer);
            stampEl.textContent = 'stamped by ' + data.model + ' · ' + (data.context_files || 0) + ' folder clues';
        }
    } catch (e) {
        typing.remove();
        history.pop();
        bubble('assistant', '❌ Server did not respond — is FileSeek still running?');
    } finally {
        setBusy(false);
    }
}

formEl.addEventListener('submit', (event) => {
    event.preventDefault();
    const question = inputEl.value.trim();
    if (!question) return;
    inputEl.value = '';
    sendQuestion(question);
});

compareBtnEl.addEventListener('click', async () => {
    if (!filePath || compareBtnEl.disabled) return;
    compareBtnEl.disabled = true;
    try {
        const res = await fetch('/api/compare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filePath })
        });
        const data = await res.json();
        if (!data.ok) {
            bubble('assistant', '❌ ' + (data.error || 'Compare did not come back — try again.'));
            return;
        }
        if (data.sensitive && !window.confirm('This file is marked sensitive.\nOnly its name, type and size would leave this machine — never its content.\nOpen the cloud AIs anyway?')) {
            return;
        }
        data.links.forEach(link => window.open(link.url, '_blank'));
        bubble('assistant', '☁ Opened ' + data.links.length + ' cloud AIs in new tabs — they see only the file’s name, type and size. Its content never leaves this machine.');
    } catch (e) {
        bubble('assistant', '❌ Server did not respond — is FileSeek still running?');
    } finally {
        compareBtnEl.disabled = false;
    }
});

(async () => {
    if (!filePath) {
        nameEl.textContent = 'No file selected';
        bubble('assistant', 'Open a conversation from the catalog’s Ask panel (⛶ Full chat).');
        setBusy(true);
        return;
    }
    try {
        const res = await fetch('/api/file-card?path=' + encodeURIComponent(filePath));
        const data = await res.json();
        if (!data.ok) {
            nameEl.textContent = 'File not found';
            bubble('assistant', '❌ ' + (data.error || 'This file is no longer on disk.'));
            setBusy(true);
            return;
        }
        nameEl.textContent = data.name;
        pathEl.textContent = data.path;
        iconEl.textContent = data.icon || '🗂️';
        document.title = 'FileSeek — ' + data.name;
        if (data.sensitive) sensitiveEl.hidden = false;
        sendQuestion('What is this file and what does it do?');
    } catch (e) {
        nameEl.textContent = 'Server offline';
        bubble('assistant', '❌ Server did not respond — is FileSeek still running?');
        setBusy(true);
    }
})();

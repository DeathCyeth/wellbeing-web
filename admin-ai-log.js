(function () {
    const errEl = document.getElementById('adminAiError');
    const results = document.getElementById('adminAiResults');
    const listEl = document.getElementById('adminAiList');
    const countEl = document.getElementById('adminAiCount');
    const filterSourceEl = document.getElementById('adminAiFilterSource');
    const errorsOnlyEl = document.getElementById('adminAiErrorsOnly');
    const searchEl = document.getElementById('adminAiSearch');
    const loadBtn = document.getElementById('adminAiLoadBtn');
    const exportBtn = document.getElementById('adminAiExportBtn');

    if (!loadBtn || typeof apiService === 'undefined') return;

    let lastItems = [];
    let debounceTimer = null;

    function adminCredentials() {
        const username = document.getElementById('adminFbUsername');
        const password = document.getElementById('adminFbPassword');
        return {
            username: username ? username.value.trim() : '',
            password: password ? password.value : '',
        };
    }

    function escapeHtml(s) {
        if (s == null) return '';
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function formatWhen(ms) {
        if (ms == null) return '';
        const d = new Date(Number(ms));
        if (Number.isNaN(d.getTime())) return String(ms);
        return d.toLocaleString();
    }

    function csvEscape(cell) {
        const s = String(cell == null ? '' : cell);
        if (/[",\r\n]/.test(s)) {
            return '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
    }

    function renderList(items) {
        countEl.textContent = '(' + items.length + ')';
        lastItems = items;
        if (!items.length) {
            listEl.innerHTML = '<p style="color: var(--text-light);">No AI exchanges logged yet.</p>';
            return;
        }
        listEl.innerHTML = items
            .map(function (row) {
                const failed = !row.success || (row.error_message && row.error_message.trim());
                const border = failed ? 'border-color: #f87171; background: #fff5f5;' : 'border-color: var(--border-color); background: #fafbff;';
                const status = failed
                    ? '<span style="color:#b91c1c;font-weight:600;">Failed</span>'
                    : '<span style="color:#15803d;font-weight:600;">OK</span>';
                const ctx = row.context_username && row.context_username !== row.username
                    ? ' · patient context: <strong>' + escapeHtml(row.context_username) + '</strong>'
                    : '';
                const refs = row.references_count ? ' · ' + row.references_count + ' PubMed ref(s)' : '';
                const model = row.model ? ' · ' + escapeHtml(row.model) : '';
                const img = row.had_image ? ' · image' : '';
                return (
                    '<article class="admin-ai-log-card" style="border: 1px solid; border-radius: 8px; padding: 14px; margin-bottom: 14px; ' + border + '">' +
                    '<div style="display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; font-size:0.85rem; color:var(--text-light); margin-bottom:10px;">' +
                    '<span>' + status + ' · <strong>' + escapeHtml(row.username) + '</strong> · ' +
                    escapeHtml(row.source || '') + ctx + refs + model + img + '</span>' +
                    '<span>#' + escapeHtml(String(row.id)) + ' · ' + escapeHtml(formatWhen(row.created_at)) + '</span></div>' +
                    '<div style="margin-bottom:10px;"><strong style="font-size:0.8rem; color:var(--primary-color);">Question</strong>' +
                    '<div style="white-space:pre-wrap; margin-top:4px; line-height:1.5;">' + escapeHtml(row.question || '') + '</div></div>' +
                    (failed
                        ? '<div style="margin-bottom:10px;"><strong style="font-size:0.8rem; color:#b91c1c;">Error</strong>' +
                          '<div style="white-space:pre-wrap; margin-top:4px; color:#b91c1c;">' + escapeHtml(row.error_message || 'Unknown error') + '</div></div>'
                        : '') +
                    '<div><strong style="font-size:0.8rem; color:var(--primary-color);">AI response</strong>' +
                    '<div style="white-space:pre-wrap; margin-top:4px; line-height:1.5; max-height:320px; overflow-y:auto;">' +
                    escapeHtml(row.response || '(empty)') + '</div></div>' +
                    '</article>'
                );
            })
            .join('');
    }

    async function loadAiLog() {
        if (errEl) errEl.textContent = '';
        const cred = adminCredentials();
        if (!cred.username || !cred.password) {
            if (errEl) errEl.textContent = 'Enter admin username and password above first.';
            if (results) results.style.display = 'none';
            return;
        }
        loadBtn.disabled = true;
        try {
            const data = await apiService.listAiChatLogsAdmin({
                username: cred.username,
                password: cred.password,
                filter_source: (filterSourceEl && filterSourceEl.value) || '',
                errors_only: !!(errorsOnlyEl && errorsOnlyEl.checked),
                search: (searchEl && searchEl.value.trim()) || '',
            });
            renderList(data.items || []);
            if (results) results.style.display = 'block';
        } catch (ex) {
            if (errEl) errEl.textContent = ex.message || String(ex);
            if (results) results.style.display = 'none';
        } finally {
            loadBtn.disabled = false;
        }
    }

    loadBtn.addEventListener('click', loadAiLog);

    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            if (!lastItems.length) return;
            const header = [
                'id', 'created_at', 'username', 'source', 'success', 'error_message',
                'model', 'references_count', 'question', 'response',
            ];
            const lines = [header.join(',')].concat(
                lastItems.map(function (row) {
                    return [
                        csvEscape(row.id),
                        csvEscape(row.created_at),
                        csvEscape(row.username),
                        csvEscape(row.source),
                        csvEscape(row.success ? 1 : 0),
                        csvEscape(row.error_message),
                        csvEscape(row.model),
                        csvEscape(row.references_count),
                        csvEscape(row.question),
                        csvEscape(row.response),
                    ].join(',');
                })
            );
            const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'wellbeing-ai-chat-log.csv';
            a.click();
            URL.revokeObjectURL(a.href);
        });
    }

    function scheduleReload() {
        const cred = adminCredentials();
        if (!cred.username || !cred.password) return;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(loadAiLog, 450);
    }

    if (filterSourceEl) filterSourceEl.addEventListener('change', scheduleReload);
    if (errorsOnlyEl) errorsOnlyEl.addEventListener('change', scheduleReload);
    if (searchEl) searchEl.addEventListener('input', scheduleReload);
})();

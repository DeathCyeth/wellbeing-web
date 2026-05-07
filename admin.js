(function () {
    const form = document.getElementById('adminFeedbackLoginForm');
    const errEl = document.getElementById('adminFbError');
    const results = document.getElementById('adminFbResults');
    const listEl = document.getElementById('adminFbList');
    const countEl = document.getElementById('adminFbCount');
    const filterSourceEl = document.getElementById('adminFbFilterSource');
    const filterRoleEl = document.getElementById('adminFbFilterRole');
    const searchEl = document.getElementById('adminFbSearch');
    const exportBtn = document.getElementById('adminFbExportBtn');

    let lastItems = [];
    let debounceTimer = null;

    function credentialsReady() {
        const username = document.getElementById('adminFbUsername').value.trim();
        const password = document.getElementById('adminFbPassword').value;
        return !!(username && password);
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
            listEl.innerHTML = '<p style="color: var(--text-light);">No feedback yet.</p>';
            return;
        }
        listEl.innerHTML = items
            .map(function (row) {
                return (
                    '<article class="admin-feedback-card" style="border: 1px solid var(--border-color); border-radius: 8px; padding: 14px; margin-bottom: 12px; background: #fafbff;">' +
                    '<div style="display:flex; flex-wrap:wrap; justify-content:space-between; gap:8px; font-size:0.85rem; color:var(--text-light); margin-bottom:8px;">' +
                    '<span><strong>' +
                    escapeHtml(row.username) +
                    '</strong> · ' +
                    escapeHtml(row.role || '') +
                    ' · ' +
                    escapeHtml(row.source || '') +
                    '</span>' +
                    '<span>' +
                    escapeHtml(formatWhen(row.created_at)) +
                    '</span></div>' +
                    '<div style="white-space: pre-wrap; line-height: 1.5;">' +
                    escapeHtml(row.message || '') +
                    '</div></article>'
                );
            })
            .join('');
    }

    async function loadFeedback() {
        errEl.textContent = '';
        if (!credentialsReady()) {
            results.style.display = 'none';
            return;
        }
        results.style.display = 'none';
        const username = document.getElementById('adminFbUsername').value.trim();
        const password = document.getElementById('adminFbPassword').value;
        const btn = document.getElementById('adminFbLoadBtn');
        btn.disabled = true;
        try {
            const data = await apiService.listFeedbackAdmin({
                username,
                password,
                filter_source: (filterSourceEl && filterSourceEl.value) || '',
                filter_role: (filterRoleEl && filterRoleEl.value) || '',
                search: (searchEl && searchEl.value.trim()) || '',
            });
            const items = data.items || [];
            renderList(items);
            results.style.display = 'block';
        } catch (ex) {
            errEl.textContent = ex.message || String(ex);
        } finally {
            btn.disabled = false;
        }
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        loadFeedback();
    });

    if (exportBtn) {
        exportBtn.addEventListener('click', function () {
            if (!lastItems.length) {
                return;
            }
            const header = ['id', 'username', 'role', 'source', 'created_at', 'message'];
            const lines = [header.join(',')].concat(
                lastItems.map(function (row) {
                    return [
                        csvEscape(row.id),
                        csvEscape(row.username),
                        csvEscape(row.role),
                        csvEscape(row.source),
                        csvEscape(row.created_at),
                        csvEscape(row.message),
                    ].join(',');
                })
            );
            const blob = new Blob([lines.join('\r\n')], {
                type: 'text/csv;charset=utf-8',
            });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'wellbeing-feedback.csv';
            a.click();
            URL.revokeObjectURL(a.href);
        });
    }

    function scheduleReload() {
        if (!credentialsReady()) return;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(loadFeedback, 450);
    }

    function refetchIfReady() {
        if (credentialsReady()) loadFeedback();
    }

    if (filterSourceEl) filterSourceEl.addEventListener('change', refetchIfReady);
    if (filterRoleEl) filterRoleEl.addEventListener('change', refetchIfReady);
    if (searchEl) searchEl.addEventListener('input', scheduleReload);
})();

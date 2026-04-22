(function () {
    const form = document.getElementById('adminFeedbackLoginForm');
    const errEl = document.getElementById('adminFbError');
    const results = document.getElementById('adminFbResults');
    const listEl = document.getElementById('adminFbList');
    const countEl = document.getElementById('adminFbCount');

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

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        errEl.textContent = '';
        results.style.display = 'none';
        const username = document.getElementById('adminFbUsername').value.trim();
        const password = document.getElementById('adminFbPassword').value;
        const btn = document.getElementById('adminFbLoadBtn');
        btn.disabled = true;
        try {
            const data = await apiService.listFeedbackAdmin({ username, password });
            const items = data.items || [];
            countEl.textContent = '(' + items.length + ')';
            if (!items.length) {
                listEl.innerHTML = '<p style="color: var(--text-light);">No feedback yet.</p>';
            } else {
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
            results.style.display = 'block';
        } catch (ex) {
            errEl.textContent = ex.message || String(ex);
        } finally {
            btn.disabled = false;
        }
    });
})();

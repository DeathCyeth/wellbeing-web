(function () {
    var m = location.pathname.match(/^\/console\/([^/]+)/);
    var back = document.getElementById('adminSetupBackLink');
    if (m && back) {
        back.href = '/console/' + m[1] + '/';
    } else if (back) {
        back.href = '/admin.html';
    }

    (async function loadServerHints() {
        var el = document.getElementById('adminSetupServerHints');
        if (!el || typeof apiService === 'undefined') return;
        try {
            var c = await apiService.getFeedbackConfig();
            var parts = [];
            if (!c.bootstrap_key_configured) {
                parts.push(
                    '<strong>Bootstrap is not enabled on the server.</strong> In your host (e.g. Render) add environment variable <code>ADMIN_BOOTSTRAP_KEY</code> to any long random value, save, then <strong>redeploy</strong> the web service.'
                );
            }
            if (c.uses_private_console) {
                parts.push(
                    '<strong>Private admin URL is on</strong> (<code>ADMIN_ACCESS_SECRET</code> is set). Use your private link <code>…/console/&lt;secret&gt;/create</code> — this <code>/admin-setup.html</code> page may be disabled until you clear that secret.'
                );
            }
            if (c.notification_webhook_configured) {
                parts.push(
                    '<code>FEEDBACK_NOTIFY_WEBHOOK</code> is set: each new feedback is also POSTed there as JSON (good for Slack/Zapier).'
                );
            }
            if (!c.feedback_admin_usernames_configured) {
                parts.push(
                    'Tip: add <code>FEEDBACK_ADMIN_USERNAMES</code> (comma-separated doctor usernames) so those accounts can open the feedback inbox without an Admin role.'
                );
            }
            if (parts.length) {
                el.innerHTML =
                    '<div style="background:#fffbeb;padding:14px;border-radius:8px;font-size:0.88rem;line-height:1.45;border:1px solid #fcd34d;color:#78350f;">' +
                    parts.join('<br><br>') +
                    '</div>';
            }
        } catch (e) {
            /* ignore */
        }
    })();

    var form = document.getElementById('adminBootstrapForm');
    var errEl = document.getElementById('adminBootstrapError');
    var okEl = document.getElementById('adminBootstrapOk');

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        errEl.textContent = '';
        okEl.style.display = 'none';
        var k = document.getElementById('bootstrapKey').value;
        var name = document.getElementById('adminNewName').value.trim();
        var username = document.getElementById('adminNewUsername').value.trim();
        var p1 = document.getElementById('adminNewPassword').value;
        var p2 = document.getElementById('adminNewPassword2').value;
        if (p1 !== p2) {
            errEl.textContent = 'Passwords do not match.';
            return;
        }
        var btn = document.getElementById('adminBootstrapSubmit');
        btn.disabled = true;
        try {
            var res = await apiService.createAdminBootstrap({
                bootstrap_key: k,
                username: username,
                password: p1,
                name: name,
            });
            okEl.textContent = res.message || 'Created.';
            okEl.style.display = 'block';
            form.reset();
        } catch (ex) {
            errEl.textContent = ex.message || String(ex);
        } finally {
            btn.disabled = false;
        }
    });
})();

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
            if (c.literature_notify_webhook_configured) {
                parts.push(
                    '<code>LITERATURE_NOTIFY_WEBHOOK</code> is set: adding a PMID to the repository POSTs JSON there (Discord/Slack/Zapier for team tracking).'
                );
            }
            if (c.feedback_email_smtp_configured) {
                parts.push(
                    '<code>FEEDBACK_EMAIL_TO</code> + SMTP is set: each new feedback is also emailed to that address (in addition to the database).'
                );
            }
            if (!c.notification_webhook_configured && !c.feedback_email_smtp_configured) {
                parts.push(
                    'To get alerts without opening this page, set <code>FEEDBACK_NOTIFY_WEBHOOK</code> (Slack/Zapier) and/or email: <code>FEEDBACK_EMAIL_TO</code>, <code>FEEDBACK_EMAIL_FROM</code>, <code>FEEDBACK_SMTP_HOST</code>, <code>FEEDBACK_SMTP_USER</code>, <code>FEEDBACK_SMTP_PASSWORD</code> (port defaults to 587; use <code>FEEDBACK_SMTP_USE_SSL=1</code> for port 465).'
                );
            }
            if (!c.feedback_auth_secret_configured) {
                parts.push(
                    '<strong>Recommended for production:</strong> set <code>FEEDBACK_AUTH_SECRET</code> (long random value) so in-app feedback keeps working after deploys and across multiple workers. Without it, users may see “feedback session no longer matches the server” until they log out and back in. See <code>PAID_DEPLOYMENT.md</code> Step 2.4b.'
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

(function () {
    var m = location.pathname.match(/^\/console\/([^/]+)/);
    var back = document.getElementById('adminSetupBackLink');
    if (m && back) {
        back.href = '/console/' + m[1] + '/';
    } else if (back) {
        back.href = '/admin.html';
    }

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

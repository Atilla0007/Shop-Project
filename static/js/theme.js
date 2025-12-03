(() => {
    const body = document.body;
    const toggleBtn = document.getElementById('theme-toggle');
    const saved = localStorage.getItem('theme');

    function applyTheme(theme) {
        if (theme === 'light') {
            body.classList.remove('theme-dark');
            body.classList.add('theme-light');
        } else {
            body.classList.remove('theme-light');
            body.classList.add('theme-dark');
        }
        localStorage.setItem('theme', theme);
        if (toggleBtn) toggleBtn.textContent = theme === 'light' ? '☼' : '☾';
    }

    if (saved === 'light' || saved === 'dark') {
        applyTheme(saved);
    } else {
        applyTheme('dark');
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const next = body.classList.contains('theme-dark') ? 'light' : 'dark';
            applyTheme(next);
        });
    }
})();

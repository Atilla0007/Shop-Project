document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('app-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const toggle = document.getElementById('sidebar-toggle');
    const closeBtn = document.getElementById('sidebar-close');

    const openSidebar = () => {
        if (!sidebar) return;
        sidebar.classList.add('open');
        overlay?.classList.add('show');
    };

    const closeSidebar = () => {
        if (!sidebar) return;
        sidebar.classList.remove('open');
        overlay?.classList.remove('show');
    };

    toggle?.addEventListener('click', openSidebar);
    closeBtn?.addEventListener('click', closeSidebar);
    overlay?.addEventListener('click', closeSidebar);

    document.addEventListener('keyup', (event) => {
        if (event.key === 'Escape') {
            closeSidebar();
        }
    });
});

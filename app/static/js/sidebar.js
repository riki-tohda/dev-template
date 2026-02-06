/**
 * POL Portal - Sidebar Control
 */

function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebarOverlay');
    var appContainer = document.querySelector('.app-container');
    var isMobile = window.innerWidth <= 768;
    var isTablet = window.innerWidth <= 1024 && window.innerWidth > 768;

    if (isMobile) {
        sidebar.classList.toggle('expanded');
        overlay.classList.toggle('active');
        document.body.style.overflow = sidebar.classList.contains('expanded') ? 'hidden' : '';
    } else if (isTablet) {
        sidebar.classList.toggle('expanded');
        localStorage.setItem('sidebarExpanded', sidebar.classList.contains('expanded'));
    } else {
        sidebar.classList.toggle('collapsed');
        appContainer.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    }
}

function closeSidebar() {
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.remove('expanded');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
}

function initSidebar() {
    var sidebar = document.getElementById('sidebar');
    if (!sidebar) return;

    var appContainer = document.querySelector('.app-container');
    var isMobile = window.innerWidth <= 768;
    var isTablet = window.innerWidth <= 1024 && window.innerWidth > 768;

    if (isMobile) {
        sidebar.classList.remove('collapsed', 'expanded');
        if (appContainer) appContainer.classList.remove('sidebar-collapsed');
    } else if (isTablet) {
        sidebar.classList.remove('collapsed');
        if (appContainer) appContainer.classList.remove('sidebar-collapsed');
    } else {
        sidebar.classList.remove('expanded');
        var isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (isCollapsed) {
            sidebar.classList.add('collapsed');
            if (appContainer) appContainer.classList.add('sidebar-collapsed');
        } else {
            sidebar.classList.remove('collapsed');
            if (appContainer) appContainer.classList.remove('sidebar-collapsed');
        }
    }
}

document.addEventListener('DOMContentLoaded', initSidebar);

var resizeTimeout;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(initSidebar, 150);
});

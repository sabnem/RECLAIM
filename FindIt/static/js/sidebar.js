(() => {
    const sidebar = document.getElementById('appSidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    const collapse = document.getElementById('sidebarCollapseToggle');
    const opener = document.getElementById('sidebarMobileOpen');
    const closer = document.getElementById('sidebarMobileClose');
    const mobile = matchMedia('(max-width: 991.98px)');
    const background = [...document.querySelectorAll('.mobile-topbar, .app-main, .app-shell > .footer')];
    let collapsed = false;
    let previousFocus;
    try { collapsed = localStorage.getItem('sidebar-state') === 'collapsed'; } catch (_) {}

    function setCollapsed(value, persist = true) {
        collapsed = value;
        document.body.classList.toggle('sidebar-collapsed', value && !mobile.matches);
        collapse.setAttribute('aria-expanded', String(!value));
        collapse.setAttribute('aria-label', value ? 'Expand menu' : 'Collapse menu');
        collapse.title = value ? 'Expand menu' : 'Collapse menu';
        if (persist) {
            try { localStorage.setItem('sidebar-state', value ? 'collapsed' : 'expanded'); } catch (_) {}
        }
    }

    function setDrawer(open, restoreFocus = true) {
        open = open && mobile.matches;
        const wasOpen = sidebar.classList.contains('is-open');
        if (open && !wasOpen) previousFocus = document.activeElement;
        sidebar.inert = mobile.matches && !open;
        sidebar.classList.toggle('is-open', open);
        backdrop.classList.toggle('active', open);
        document.body.classList.toggle('sidebar-drawer-open', open);
        opener.setAttribute('aria-expanded', String(open));
        background.forEach(element => { element.inert = open; });
        if (open) {
            sidebar.setAttribute('role', 'dialog');
            sidebar.setAttribute('aria-modal', 'true');
            closer.focus();
        } else {
            sidebar.removeAttribute('role');
            sidebar.removeAttribute('aria-modal');
            if (wasOpen && restoreFocus) (previousFocus || opener).focus();
        }
    }

    [opener, closer, collapse].forEach(button => button.setAttribute('aria-controls', sidebar.id));
    sidebar.querySelectorAll('[data-tooltip]').forEach(item => { item.title = item.dataset.tooltip; });
    sidebar.querySelectorAll('a.active, a.active-link').forEach(link => link.setAttribute('aria-current', 'page'));
    sidebar.querySelectorAll('[data-submenu-target]').forEach(button => {
        const submenu = document.getElementById(button.dataset.submenuTarget);
        button.setAttribute('aria-controls', submenu.id);
        button.addEventListener('click', () => {
            if (!mobile.matches && collapsed) setCollapsed(false);
            const open = button.getAttribute('aria-expanded') !== 'true';
            button.setAttribute('aria-expanded', String(open));
            submenu.classList.toggle('open', open);
            button.closest('.sidebar-group').classList.toggle('open', open);
        });
    });
    // Fade hints on the scrollable category list show that more items are available.
    const categoryList = sidebar.querySelector('[data-category-list]');
    function updateCategoryHints() {
        if (!categoryList) return;
        const { scrollTop, scrollHeight, clientHeight } = categoryList;
        categoryList.classList.toggle('can-scroll-up', scrollTop > 2);
        categoryList.classList.toggle('can-scroll-down', scrollTop + clientHeight < scrollHeight - 2);
    }
    categoryList?.addEventListener('scroll', updateCategoryHints, { passive: true });
    sidebar.querySelector('[data-submenu-target="categoriesSubmenu"]')?.addEventListener('click', () => requestAnimationFrame(updateCategoryHints));

    const categoryFilter = sidebar.querySelector('[data-category-filter]');
    categoryFilter?.addEventListener('input', () => {
        const query = categoryFilter.value.trim().toLowerCase();
        let shown = 0;
        categoryList.querySelectorAll('a.account-menu-link').forEach(link => {
            const match = link.textContent.trim().toLowerCase().includes(query);
            link.hidden = !match;
            if (match) shown += 1;
        });
        categoryList.querySelector('[data-category-empty]').hidden = shown > 0;
        categoryList.scrollTop = 0;
        updateCategoryHints();
    });

    const scrollArea = sidebar.querySelector('.app-sidebar-scroll');
    scrollArea?.addEventListener('scroll', () => {
        sidebar.querySelector('.app-sidebar-shell').classList.toggle('is-scrolled', scrollArea.scrollTop > 4);
    }, { passive: true });

    collapse.addEventListener('click', () => setCollapsed(!collapsed));
    opener.addEventListener('click', () => setDrawer(true));
    closer.addEventListener('click', () => setDrawer(false));
    backdrop.addEventListener('click', () => setDrawer(false));
    sidebar.addEventListener('click', event => {
        if (mobile.matches && event.target.closest('a[href]')) setDrawer(false);
    });
    document.addEventListener('keydown', event => {
        if (!sidebar.classList.contains('is-open')) return;
        if (event.key === 'Escape') { event.preventDefault(); setDrawer(false); }
        if (event.key === 'Tab') {
            const focusable = [...sidebar.querySelectorAll('a[href], button:not([disabled])')]
                .filter(element => element.getClientRects().length > 0);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    });
    function syncLayout() {
        const focusWasInside = sidebar.contains(document.activeElement);
        setDrawer(false, false);
        setCollapsed(collapsed, false);
        if (mobile.matches && focusWasInside) opener.focus();
        else if (!mobile.matches && document.activeElement === opener) collapse.focus();
    }
    mobile.addEventListener('change', syncLayout);
    syncLayout();
})();

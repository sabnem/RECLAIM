// Restore the saved theme; default to light.
(function(){
    const toggle = document.getElementById('darkModeToggle');
    const icon = document.getElementById('darkModeIcon');
    let saved;
    try { saved = localStorage.getItem('site-theme'); } catch (_) {}

    function setDark(enabled, persist=true){
        document.documentElement.setAttribute('data-bs-theme', enabled ? 'dark' : 'light');
        if(enabled) document.body.classList.add('dark-mode'); else document.body.classList.remove('dark-mode');
        if(enabled){ icon.className = 'bi bi-sun-fill'; toggle.classList.remove('btn-outline-secondary'); toggle.classList.add('btn-outline-light'); }
        else { icon.className = 'bi bi-moon-fill'; toggle.classList.remove('btn-outline-light'); toggle.classList.add('btn-outline-secondary'); }
        toggle.querySelector('.sidebar-footer-label').textContent = enabled ? 'Dark mode' : 'Light mode';
        toggle.setAttribute('aria-label', enabled ? 'Switch to light mode' : 'Switch to dark mode');
        toggle.title = toggle.getAttribute('aria-label');
        if(persist) { try { localStorage.setItem('site-theme', enabled ? 'dark' : 'light'); } catch (_) {} }
    }

    // initialize
    if(saved === 'dark') setDark(true, false); else setDark(false, false);

    // click handler
    toggle && toggle.addEventListener('click', function(){ setDark(!document.body.classList.contains('dark-mode')); });
})();

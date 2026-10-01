(() => {
  const badge = document.getElementById('claimNotificationCount');
  if (!badge) return;
  async function update() {
    if (document.hidden) return;
    try {
      const response = await fetch(badge.dataset.url, {headers: {'Accept': 'application/json'}});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const {count} = await response.json();
      badge.textContent = count ? String(count) : '';
      badge.hidden = !count;
    } catch (_) { /* The next poll retries after a temporary connection failure. */ }
  }
  setInterval(update, 30000);
  window.addEventListener('pageshow', event => {
    if (event.persisted && document.getElementById('notificationList')) {
      window.location.reload();
      return;
    }
    update();
  });
  document.addEventListener('visibilitychange', update);
})();

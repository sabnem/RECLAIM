(() => {
  const panel = document.getElementById('niulizePanel');
  const open = document.getElementById('niulizeOpen');
  const form = document.getElementById('niulizeForm');
  const input = document.getElementById('niulizeQuestion');
  const log = document.getElementById('niulizeMessages');
  const status = document.getElementById('niulizeStatus');
  const buttons = [...panel.querySelectorAll('.niulize-topics button'), document.getElementById('niulizeSend')];
  let busy = false;
  let lastQuestion = '';
  const followup = document.getElementById('niulizeFollowup');
  const suggestions = document.getElementById('niulizeSuggestions');
  const requestButton = document.getElementById('niulizeRequest');
  const details = document.getElementById('niulizeRequestDetails');
  open.addEventListener('click', () => { panel.showModal(); open.setAttribute('aria-expanded', 'true'); input.focus(); });
  document.getElementById('niulizeClose').addEventListener('click', () => panel.close());
  panel.addEventListener('close', () => { open.setAttribute('aria-expanded', 'false'); open.focus(); });
  function bubble(text, own = false) {
    const p = document.createElement('p');
    p.className = 'niulize-bubble' + (own ? ' niulize-own' : '');
    p.textContent = text;
    log.append(p);
    while (log.children.length > 41) log.firstElementChild.remove();
    log.scrollTop = log.scrollHeight;
  }
  async function send(message) {
    if (busy || !message.trim()) return;
    followup.hidden = true;
    details.open = false;
    busy = true; buttons.forEach(button => button.disabled = true);
    input.readOnly = true;
    bubble(message, true); status.textContent = 'Finding a help topic…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(form.action, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value},
        body: JSON.stringify({message})
      });
      if (!response.ok) throw new Error('Unavailable');
      const data = await response.json();
      if (typeof data.response !== 'string') throw new Error('Invalid response');
      bubble(data.response); input.value = ''; status.textContent = '';
      lastQuestion = message;
      suggestions.replaceChildren();
      for (const title of (data.suggestions || []).slice(0, 3)) {
        const button = document.createElement('button');
        button.type = 'button'; button.textContent = title;
        button.addEventListener('click', () => send(title));
        suggestions.append(button);
      }
      requestButton.disabled = false;
      followup.hidden = false;
    } catch (_) {
      input.value = message;
      status.textContent = 'Help is temporarily unavailable. Your question is kept below—please try again.';
    } finally {
      clearTimeout(timeout); busy = false; input.readOnly = false;
      buttons.forEach(button => button.disabled = false);
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); send(input.value.trim()); });
  requestButton.addEventListener('click', async () => {
    if (busy || !lastQuestion) return;
    busy = true; requestButton.disabled = true;
    buttons.forEach(button => button.disabled = true);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(requestButton.dataset.url, {
        method: 'POST', credentials: 'same-origin', signal: controller.signal,
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value},
        body: JSON.stringify({message: lastQuestion})
      });
      const data = await response.json();
      status.textContent = response.ok ? data.message : data.error;
      if (response.status === 401) {
        const link = document.createElement('a');
        link.href = data.login_url; link.textContent = ' Sign in'; status.append(link);
      }
      requestButton.disabled = response.ok;
    } catch (_) {
      status.textContent = 'Could not send your request. Please try again.';
      requestButton.disabled = false;
    } finally {
      clearTimeout(timeout); busy = false;
      buttons.forEach(button => button.disabled = false);
    }
  });
  panel.querySelectorAll('.niulize-topics button').forEach(button => button.addEventListener('click', () => send(button.textContent)));
})();

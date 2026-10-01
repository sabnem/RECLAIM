// Active conversation: rendering, sending, read receipts, typing, edit/delete and offline sync.
(() => {
  const userId = Inbox.userId;
  const itemId = Number(inboxConfig.itemId);
  const recipientId = Number(inboxConfig.recipientId);
  const history = document.getElementById('chatHistory');
  const container = document.getElementById('chatMessages');
  const typingBubble = document.getElementById('typingBubble');
  const statusDefault = document.querySelector('#chatStatus .status-default');
  const statusTyping = document.querySelector('#chatStatus .status-typing');
  const connectionNote = document.getElementById('chatConnection');
  const form = document.getElementById('chatForm');
  const input = form.querySelector('[name="message"]');
  const fileInput = document.getElementById('chatImageUpload');
  const messages = new Map();
  let pendingCounter = 0;

  const belongsHere = message => message.item_id === itemId &&
    ((message.sender_id === userId && message.recipient_id === recipientId) ||
     (message.sender_id === recipientId && message.recipient_id === userId));

  // ----- Rendering -----
  function dayLabel(date) {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (date.toDateString() === now.toDateString()) return 'Today';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return date.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric', year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric' });
  }

  function timeLabel(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function tickIcon(message) {
    if (message.pending) return '<i class="bi bi-clock msg-tick" title="Sending" aria-label="Sending"></i>';
    if (message.is_read) return '<i class="bi bi-check2-all msg-tick is-read" title="Read" aria-label="Read"></i>';
    return '<i class="bi bi-check2 msg-tick" title="Sent" aria-label="Sent"></i>';
  }

  function buildBubble(message) {
    const mine = message.sender_id === userId;
    const row = document.createElement('div');
    row.className = 'msg-row ' + (mine ? 'is-sent' : 'is-received');
    row.dataset.messageId = message.id;
    row.dataset.day = new Date(message.timestamp).toDateString();

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble' + (message.deleted_for_everyone ? ' is-deleted' : '') + (message.pending ? ' is-pending' : '');

    if (editing && editing.id === String(message.id) && !message.deleted_for_everyone) {
      bubble.classList.add('is-editing');
      bubble.appendChild(buildEditor(message));
      row.appendChild(bubble);
      return row;
    }

    if (message.deleted_for_everyone) {
      const text = document.createElement('div');
      text.className = 'msg-text';
      text.innerHTML = '<i class="bi bi-slash-circle" aria-hidden="true"></i> ';
      text.append(mine ? 'You deleted this message' : 'This message was deleted');
      bubble.appendChild(text);
    } else {
      if (message.image) {
        const img = document.createElement('img');
        img.className = 'msg-image';
        img.src = message.image;
        img.alt = 'Shared image';
        img.loading = 'lazy';
        img.addEventListener('click', () => openLightbox(message.image));
        bubble.appendChild(img);
      }
      if (message.content) {
        const text = document.createElement('div');
        text.className = 'msg-text';
        text.textContent = message.content;
        bubble.appendChild(text);
      }
    }

    const meta = document.createElement('span');
    meta.className = 'msg-meta';
    if (message.edited && !message.deleted_for_everyone) meta.insertAdjacentHTML('beforeend', '<span class="msg-edited">edited</span>');
    const time = document.createElement('time');
    time.dateTime = message.timestamp;
    time.textContent = timeLabel(new Date(message.timestamp));
    meta.appendChild(time);
    if (mine && !message.deleted_for_everyone) meta.insertAdjacentHTML('beforeend', tickIcon(message));
    bubble.appendChild(meta);

    if (!message.pending) {
      const menu = document.createElement('div');
      menu.className = 'msg-menu dropdown';
      menu.innerHTML =
        '<button class="msg-menu-btn" type="button" data-bs-toggle="dropdown" aria-expanded="false" aria-label="Message options">' +
        '<i class="bi bi-chevron-down"></i></button><ul class="dropdown-menu ' + (mine ? 'dropdown-menu-end' : '') + ' chat-menu"></ul>';
      const items = menu.querySelector('ul');
      const addItem = (icon, label, handler, danger) => {
        const li = document.createElement('li');
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'dropdown-item' + (danger ? ' text-danger' : '');
        btn.innerHTML = '<i class="bi ' + icon + '"></i>';
        btn.append(label);
        btn.addEventListener('click', () => handler(message.id));
        li.appendChild(btn);
        items.appendChild(li);
      };
      if (!message.deleted_for_everyone && message.content) {
        addItem('bi-copy', 'Copy', copyMessage);
        if (mine) addItem('bi-pencil', 'Edit', startEdit);
      }
      addItem('bi-trash', 'Delete', confirmDelete, true);
      bubble.appendChild(menu);
    }

    row.appendChild(bubble);
    return row;
  }

  function nearBottom() {
    return history.scrollHeight - history.scrollTop - history.clientHeight < 120;
  }

  function scrollToBottom() {
    history.scrollTop = history.scrollHeight;
  }

  // Rebuilds the list from the message map; conversations are small enough to keep this simple.
  function renderAll() {
    const keepBottom = nearBottom();
    const sorted = [...messages.values()].sort((a, b) =>
      new Date(a.timestamp) - new Date(b.timestamp) || String(a.id).localeCompare(String(b.id), undefined, { numeric: true }));
    const fragment = document.createDocumentFragment();
    let lastDay = null;
    sorted.forEach(message => {
      const day = new Date(message.timestamp).toDateString();
      if (day !== lastDay) {
        const divider = document.createElement('div');
        divider.className = 'date-divider';
        divider.innerHTML = '<span></span>';
        divider.firstChild.textContent = dayLabel(new Date(message.timestamp));
        fragment.appendChild(divider);
        lastDay = day;
      }
      fragment.appendChild(buildBubble(message));
    });
    if (!sorted.length) {
      const empty = document.createElement('div');
      empty.className = 'chat-empty-note';
      empty.innerHTML = '<i class="bi bi-lock" aria-hidden="true"></i> Say hello and arrange a safe, public meeting place for the return.';
      fragment.appendChild(empty);
    }
    container.replaceChildren(fragment);
    if (keepBottom) scrollToBottom();
  }

  function upsert(message, { scroll = false } = {}) {
    messages.set(String(message.id), message);
    renderAll();
    if (scroll) scrollToBottom();
  }

  // ----- Read receipts -----
  let readTimer = null;
  function markRead() {
    if (document.visibilityState !== 'visible') return;
    const unread = [...messages.values()].some(m => m.sender_id === recipientId && !m.is_read);
    if (!unread) return;
    clearTimeout(readTimer);
    readTimer = setTimeout(() => {
      Inbox.request(inboxConfig.readUrl, { json: { item_id: itemId, recipient_id: recipientId } })
        .then(() => messages.forEach(m => { if (m.sender_id === recipientId) m.is_read = true; }))
        .catch(() => {});
    }, 300);
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') { markRead(); sync(); }
  });

  // ----- Typing (outgoing) -----
  const TYPING_REFRESH_MS = 2500;
  const TYPING_IDLE_MS = 3000;
  let typingActive = false;
  let typingSentAt = 0;
  let typingIdle = null;

  function sendTyping(isTyping) {
    const payload = { type: 'typing', item_id: itemId, recipient_id: recipientId, is_typing: isTyping };
    if (!Inbox.send(payload)) {
      Inbox.request(inboxConfig.typingUrl, { json: payload }).catch(() => {});
    }
  }

  function typingStarted() {
    clearTimeout(typingIdle);
    if (!input.value.trim()) { typingStopped(); return; }
    const now = Date.now();
    if (!typingActive || now - typingSentAt > TYPING_REFRESH_MS) {
      typingActive = true;
      typingSentAt = now;
      sendTyping(true);
    }
    typingIdle = setTimeout(typingStopped, TYPING_IDLE_MS);
  }

  function typingStopped() {
    clearTimeout(typingIdle);
    if (!typingActive) return;
    typingActive = false;
    sendTyping(false);
  }

  // ----- Typing (incoming) -----
  let otherTypingTimer = null;
  function showOtherTyping(isTyping) {
    clearTimeout(otherTypingTimer);
    const keepBottom = nearBottom();
    statusTyping.hidden = !isTyping;
    statusDefault.hidden = isTyping;
    typingBubble.hidden = !isTyping;
    if (isTyping && keepBottom) scrollToBottom();
    // A lost "stopped typing" event must not leave the indicator on forever.
    if (isTyping) otherTypingTimer = setTimeout(() => showOtherTyping(false), 6000);
  }

  // ----- Sending -----
  function autoGrow() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
  }

  function resetComposer() {
    input.value = '';
    autoGrow();
    if (fileInput) fileInput.value = '';
    const preview = document.getElementById('imagePreviewContainer');
    if (preview) preview.style.display = 'none';
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    const text = input.value.trim();
    const file = fileInput && fileInput.files[0];
    if (!text && !file) return;

    const data = new FormData();
    data.append('item_id', itemId);
    data.append('recipient_id', recipientId);
    data.append('message', text);
    if (file) data.append('chat_image', file);

    const tempId = 'pending-' + (++pendingCounter);
    upsert({
      id: tempId, pending: true, item_id: itemId, sender_id: userId, recipient_id: recipientId,
      content: text, image: file ? URL.createObjectURL(file) : '', timestamp: new Date().toISOString(),
      edited: false, deleted_for_everyone: false, is_read: false,
    }, { scroll: true });
    resetComposer();
    typingStopped();
    input.focus();

    Inbox.request(inboxConfig.sendUrl, { body: data })
      .then(response => {
        messages.delete(tempId);
        upsert(response.message, { scroll: true });
      })
      .catch(err => {
        messages.delete(tempId);
        renderAll();
        if (!input.value) input.value = text;
        autoGrow();
        Inbox.toast('Message not sent: ' + err.message);
      });
  });

  input.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener('input', () => { autoGrow(); typingStarted(); });
  input.addEventListener('blur', typingStopped);
  window.addEventListener('pagehide', typingStopped);

  // ----- Message actions -----
  function copyMessage(id) {
    const message = messages.get(String(id));
    if (!message) return;
    navigator.clipboard?.writeText(message.content).then(() => Inbox.toast('Message copied'), () => {});
  }

  async function confirmDelete(id) {
    const message = messages.get(String(id));
    if (!message) return;
    const mine = message.sender_id === userId;
    const actions = [];
    if (mine && !message.deleted_for_everyone) actions.push({ label: 'Delete for everyone', value: 'everyone', danger: true });
    actions.push({ label: 'Delete for me', value: 'me', danger: !actions.length });
    const choice = await Inbox.dialog({
      title: 'Delete message?',
      text: mine && !message.deleted_for_everyone
        ? 'Delete for everyone removes it for ' + (inboxConfig.otherName || 'the other person') + ' too.'
        : 'This removes the message from your chat only.',
      actions,
    });
    if (!choice) return;
    try {
      const response = await Inbox.request(inboxConfig.deleteUrl, { json: { message_id: id, for_everyone: choice === 'everyone' } });
      if (choice === 'everyone') {
        upsert(response.message);
      } else {
        messages.delete(String(id));
        renderAll();
      }
    } catch (err) {
      Inbox.toast(err.message);
    }
  }

  // The open editor survives re-renders caused by incoming events.
  let editing = null; // { id, draft }

  function startEdit(id) {
    const message = messages.get(String(id));
    if (!message) return;
    editing = { id: String(id), draft: message.content };
    renderAll();
    const area = container.querySelector('.msg-editor textarea');
    area?.focus();
    area?.setSelectionRange(area.value.length, area.value.length);
  }

  function stopEdit() {
    editing = null;
    renderAll();
  }

  function buildEditor(message) {
    const editor = document.createElement('div');
    editor.className = 'msg-editor';
    editor.innerHTML =
      '<textarea class="form-control" rows="2" maxlength="4000" aria-label="Edit message"></textarea>' +
      '<div class="msg-editor-actions"><button type="button" class="btn btn-sm btn-light" data-act="cancel">Cancel</button>' +
      '<button type="button" class="btn btn-sm btn-primary" data-act="save">Save</button></div>';
    const area = editor.querySelector('textarea');
    area.value = editing.draft;
    area.addEventListener('input', () => { editing.draft = area.value; });

    const save = async () => {
      const value = area.value.trim();
      if (!value) { Inbox.toast('Message cannot be empty'); return; }
      if (value === message.content) { stopEdit(); return; }
      try {
        const response = await Inbox.request(inboxConfig.editUrl, { json: { message_id: message.id, new_content: value } });
        editing = null;
        upsert(response.message);
      } catch (err) {
        Inbox.toast(err.message);
      }
    };
    editor.querySelector('[data-act="cancel"]').addEventListener('click', stopEdit);
    editor.querySelector('[data-act="save"]').addEventListener('click', save);
    area.addEventListener('keydown', event => {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); save(); }
      if (event.key === 'Escape') { event.stopPropagation(); stopEdit(); }
    });
    return editor;
  }

  // ----- Live events -----
  Inbox.on('message', ({ message }) => {
    if (!belongsHere(message)) return;
    const incoming = message.sender_id === recipientId;
    if (incoming) showOtherTyping(false);
    upsert(message, { scroll: !incoming || nearBottom() });
    if (incoming) markRead();
  });
  Inbox.on('message_updated', ({ message }) => {
    if (belongsHere(message) && messages.has(String(message.id))) upsert(message);
  });
  Inbox.on('message_hidden', ({ message_id }) => {
    if (messages.delete(String(message_id))) renderAll();
  });
  Inbox.on('read', data => {
    if (data.item_id !== itemId || data.reader_id !== recipientId) return;
    const ids = new Set(data.message_ids.map(String));
    let changed = false;
    messages.forEach(m => { if (ids.has(String(m.id)) && !m.is_read) { m.is_read = true; changed = true; } });
    if (changed) renderAll();
  });
  Inbox.on('typing', data => {
    if (data.item_id === itemId && data.sender_id === recipientId) showOtherTyping(data.is_typing);
  });
  document.addEventListener('chat:cleared', () => {
    messages.clear();
    renderAll();
  });

  // ----- Offline fallback: poll while the socket is down -----
  let pollTimer = null;
  let syncing = false;
  function sync() {
    if (syncing) return;
    syncing = true;
    const url = inboxConfig.syncUrl + '?item_id=' + itemId + '&recipient_id=' + recipientId;
    Inbox.request(url, { method: 'GET' })
      .then(data => {
        const pending = [...messages.values()].filter(m => m.pending);
        messages.clear();
        data.messages.concat(pending).forEach(m => messages.set(String(m.id), m));
        renderAll();
        if (!Inbox.isSocketOpen()) showOtherTyping(data.typing);
        markRead();
      })
      .catch(() => {})
      .finally(() => { syncing = false; });
  }

  let socketState = null;
  Inbox.on('socket', open => {
    if (open === socketState) return;
    socketState = open;
    connectionNote.hidden = open;
    clearInterval(pollTimer);
    if (open) {
      sync(); // catch up on anything missed while disconnected
    } else {
      pollTimer = setInterval(() => { if (document.visibilityState === 'visible') sync(); }, 4000);
    }
  });

  // ----- Initial render -----
  JSON.parse(document.getElementById('chatMessagesData').textContent)
    .forEach(message => messages.set(String(message.id), message));
  renderAll();
  scrollToBottom();
  autoGrow();
})();

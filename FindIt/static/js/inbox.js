// Inbox shell: live socket, conversation list updates, dialogs and chat-level actions.
const inboxConfig = document.getElementById('inboxConfig').dataset;

window.Inbox = (() => {
  const userId = Number(inboxConfig.userId);
  const activeKey = inboxConfig.itemId ? inboxConfig.itemId + '-' + inboxConfig.recipientId : '';
  const listeners = {};
  let socket = null;
  let socketOpen = false;
  let retryDelay = 1000;
  let pingTimer = null;

  function on(type, fn) { (listeners[type] = listeners[type] || []).push(fn); }
  function emit(type, data) { (listeners[type] || []).forEach(fn => fn(data)); }

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss://' : 'ws://';
    try {
      socket = new WebSocket(protocol + location.host + '/ws/inbox/');
    } catch (err) {
      scheduleReconnect();
      return;
    }
    socket.onopen = () => {
      socketOpen = true;
      retryDelay = 1000;
      clearInterval(pingTimer);
      pingTimer = setInterval(() => send({ type: 'ping' }), 25000);
      emit('socket', true);
    };
    socket.onmessage = event => {
      let data;
      try { data = JSON.parse(event.data); } catch (_) { return; }
      if (data && data.type) emit(data.type, data);
    };
    socket.onclose = event => {
      const wasOpen = socketOpen;
      socketOpen = false;
      clearInterval(pingTimer);
      if (wasOpen) emit('socket', false);
      if (event.code !== 4401) scheduleReconnect();
    };
    socket.onerror = () => {};
  }

  function scheduleReconnect() {
    emit('socket', false);
    setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 30000);
  }

  function send(payload) {
    if (!socketOpen) return false;
    try { socket.send(JSON.stringify(payload)); return true; } catch (_) { return false; }
  }

  function request(url, options = {}) {
    const headers = { 'X-CSRFToken': inboxConfig.csrfToken, 'X-Requested-With': 'XMLHttpRequest' };
    let body = options.body;
    if (options.json) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(options.json);
    }
    return fetch(url, { method: options.method || 'POST', headers, body, credentials: 'same-origin' })
      .then(response => response.json().catch(() => ({})).then(data => {
        if (!response.ok || data.success === false) throw new Error(data.error || 'Something went wrong. Try again.');
        return data;
      }));
  }

  let toastTimer = null;
  function toast(text) {
    const el = document.getElementById('chatToast');
    if (!el) return;
    el.textContent = text;
    el.hidden = false;
    requestAnimationFrame(() => el.classList.add('show'));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => { el.hidden = true; }, 200);
    }, 2600);
  }

  // Resolves with the chosen action value, or null when dismissed.
  function dialog({ title, text, actions }) {
    const modalEl = document.getElementById('chatDialog');
    const holder = document.getElementById('chatDialogActions');
    document.getElementById('chatDialogTitle').textContent = title;
    const textEl = document.getElementById('chatDialogText');
    textEl.textContent = text || '';
    textEl.hidden = !text;
    holder.replaceChildren();
    return new Promise(resolve => {
      let result = null;
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      actions.concat([{ label: 'Cancel', value: null }]).forEach(action => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chat-dialog-btn' + (action.danger ? ' is-danger' : '');
        button.textContent = action.label;
        button.addEventListener('click', () => { result = action.value; modal.hide(); });
        holder.appendChild(button);
      });
      modalEl.addEventListener('hidden.bs.modal', () => resolve(result), { once: true });
      modal.show();
    });
  }

  function formatListTime(iso) {
    if (!iso) return '';
    const date = new Date(iso);
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  // ----- Conversation list -----
  const list = document.getElementById('conversationItems');
  const typingTimers = {};

  function rowFor(key) {
    return list ? list.querySelector('.convo-row[data-key="' + key + '"]') : null;
  }

  function previewFor(message) {
    if (message.deleted_for_everyone) {
      return message.sender_id === userId ? 'You deleted this message' : 'This message was deleted';
    }
    return message.content || (message.image ? 'Photo' : '');
  }

  function setRowPreview(row, message) {
    const mine = message.sender_id === userId;
    const preview = row.querySelector('.convo-preview');
    preview.classList.toggle('is-deleted', message.deleted_for_everyone);
    preview.replaceChildren();
    if (message.deleted_for_everyone) {
      preview.insertAdjacentHTML('beforeend', '<i class="bi bi-slash-circle" aria-hidden="true"></i>');
    } else if (mine) {
      preview.insertAdjacentHTML('beforeend', '<i class="bi msg-tick ' + (message.is_read ? 'bi-check2-all is-read' : 'bi-check2') + '" aria-hidden="true"></i>');
    }
    const text = document.createElement('span');
    text.className = 'convo-preview-text';
    const value = previewFor(message);
    text.textContent = value.length > 60 ? value.slice(0, 59) + '…' : value;
    preview.appendChild(text);
    row.dataset.lastId = message.id;
  }

  function buildRow(message, key) {
    const otherId = message.sender_id === userId ? message.recipient_id : message.sender_id;
    const row = document.createElement('a');
    row.className = 'conversation convo-row';
    row.dataset.key = key;
    row.href = inboxConfig.inboxUrl + '?item_id=' + message.item_id + '&recipient_id=' + otherId;
    const avatar = message.sender_avatar ||
      'https://ui-avatars.com/api/?name=' + encodeURIComponent(message.sender_name) + '&background=a9510b&color=fff&size=80';
    row.innerHTML =
      '<img class="rounded-circle conversation-avatar" width="48" height="48" alt="">' +
      '<span class="convo-body">' +
        '<span class="convo-top"><span class="convo-name"></span><time class="convo-time"></time></span>' +
        '<span class="convo-item"><i class="bi bi-tag" aria-hidden="true"></i> <span></span></span>' +
        '<span class="convo-bottom"><span class="convo-preview"></span><span class="convo-typing" hidden>typing…</span>' +
        '<span class="convo-unread" hidden>0</span></span>' +
      '</span>';
    row.querySelector('img').src = avatar;
    row.querySelector('.convo-name').textContent = message.sender_name;
    row.querySelector('.convo-item span').textContent = message.item_title;
    list.querySelector('.convo-empty')?.remove();
    return row;
  }

  on('message', ({ message }) => {
    if (!list) return;
    const mine = message.sender_id === userId;
    const otherId = mine ? message.recipient_id : message.sender_id;
    const key = message.item_id + '-' + otherId;
    let row = rowFor(key);
    if (!row) {
      // A brand-new chat can only start from the other member; archived view skips it.
      if (mine || inboxConfig.archivedView === 'true') return;
      row = buildRow(message, key);
    }
    setRowPreview(row, message);
    const time = row.querySelector('.convo-time');
    time.dateTime = message.timestamp;
    time.textContent = formatListTime(message.timestamp);
    const isActive = key === activeKey && document.visibilityState === 'visible';
    if (!mine && !isActive) {
      const badge = row.querySelector('.convo-unread');
      const count = Number(badge.textContent || 0) + 1;
      badge.textContent = count;
      badge.hidden = false;
      row.classList.add('has-unread');
    }
    showRowTyping(key, false);
    list.prepend(row);
  });

  on('message_updated', ({ message }) => {
    const otherId = message.sender_id === userId ? message.recipient_id : message.sender_id;
    const row = rowFor(message.item_id + '-' + otherId);
    if (row && String(row.dataset.lastId) === String(message.id)) setRowPreview(row, message);
  });

  on('read', data => {
    if (data.reader_id === userId) return;
    const row = rowFor(data.item_id + '-' + data.reader_id);
    if (!row || !data.message_ids.map(String).includes(String(row.dataset.lastId))) return;
    const tick = row.querySelector('.msg-tick');
    if (tick) tick.className = 'bi msg-tick bi-check2-all is-read';
  });

  function showRowTyping(key, typing) {
    const row = rowFor(key);
    if (!row) return;
    row.querySelector('.convo-typing').hidden = !typing;
    row.querySelector('.convo-preview').hidden = typing;
    clearTimeout(typingTimers[key]);
    if (typing) typingTimers[key] = setTimeout(() => showRowTyping(key, false), 6000);
  }

  on('typing', data => showRowTyping(data.item_id + '-' + data.sender_id, data.is_typing));

  on('conversation', data => {
    // Another tab of this member archived/cleared/deleted a chat.
    const key = data.item_id + '-' + data.other_user_id;
    if (key === activeKey) {
      location.href = inboxConfig.inboxUrl + '?view=list';
    } else if (data.action !== 'clear') {
      rowFor(key)?.remove();
    }
  });

  if (list) connect();

  return { userId, activeKey, on, send, request, toast, dialog, isSocketOpen: () => socketOpen, formatListTime };
})();

document.addEventListener('DOMContentLoaded', () => {
  const conversationList = document.getElementById('conversationList');
  const chatArea = document.getElementById('chatArea');
  const backToListBtn = document.getElementById('backToListBtn');
  const mobileQuery = window.matchMedia('(max-width: 767.98px)');
  let showChat = inboxConfig.hasConversation === 'true';

  function updateViewportHeight() {
    document.documentElement.style.setProperty('--app-vh', (window.visualViewport ? window.visualViewport.height : window.innerHeight) + 'px');
  }
  function initMobileView() {
    conversationList.classList.toggle('mobile-panel-hidden', mobileQuery.matches && showChat);
    chatArea.classList.toggle('mobile-panel-hidden', mobileQuery.matches && !showChat);
    updateViewportHeight();
  }
  backToListBtn?.addEventListener('click', () => {
    showChat = false;
    initMobileView();
  });
  mobileQuery.addEventListener('change', initMobileView);
  window.visualViewport?.addEventListener('resize', updateViewportHeight);
  initMobileView();

  // List timestamps in WhatsApp style (time today, "Yesterday", then date).
  document.querySelectorAll('.convo-time[data-time]').forEach(el => {
    el.textContent = Inbox.formatListTime(el.dataset.time);
  });

  // Image attachment preview
  const fileInput = document.getElementById('chatImageUpload');
  const previewContainer = document.getElementById('imagePreviewContainer');
  const previewImg = document.getElementById('chatImagePreview');
  fileInput?.addEventListener('change', function() {
    if (this.files && this.files[0]) {
      const reader = new FileReader();
      reader.onload = e => {
        previewImg.src = e.target.result;
        previewContainer.style.display = 'block';
      };
      reader.readAsDataURL(this.files[0]);
    }
  });
  document.getElementById('removeImageBtn')?.addEventListener('click', () => {
    fileInput.value = '';
    previewImg.src = '';
    previewContainer.style.display = 'none';
  });

  // Chat-level actions only ever change the current member's view.
  const otherName = inboxConfig.otherName || 'the other person';
  const chatActions = {
    archive: { title: 'Archive this chat?', text: 'It moves to Archived. ' + otherName + ' is not notified.', label: 'Archive' },
    unarchive: { title: 'Unarchive this chat?', text: 'It moves back to your chats.', label: 'Unarchive' },
    clear: { title: 'Clear this chat?', text: 'Messages are removed for you only. ' + otherName + ' will still see them.', label: 'Clear chat', danger: true },
    delete: { title: 'Delete this chat?', text: 'The chat and its messages are removed for you only. ' + otherName + ' keeps their copy. It reappears if a new message arrives.', label: 'Delete chat', danger: true },
  };
  document.querySelectorAll('[data-chat-action]').forEach(button => {
    button.addEventListener('click', async () => {
      const action = button.dataset.chatAction;
      const copy = chatActions[action];
      const choice = await Inbox.dialog({ title: copy.title, text: copy.text, actions: [{ label: copy.label, value: action, danger: copy.danger }] });
      if (!choice) return;
      try {
        await Inbox.request(inboxConfig.actionUrl, { json: { action, item_id: inboxConfig.itemId, recipient_id: inboxConfig.recipientId } });
        if (action === 'clear') {
          document.dispatchEvent(new CustomEvent('chat:cleared'));
          Inbox.toast('Chat cleared');
        } else {
          location.href = inboxConfig.inboxUrl + (action === 'unarchive' ? '?item_id=' + inboxConfig.itemId + '&recipient_id=' + inboxConfig.recipientId : '?view=list');
        }
      } catch (err) {
        Inbox.toast(err.message);
      }
    });
  });

  document.getElementById('imageLightbox')?.addEventListener('click', closeLightbox);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeLightbox();
  });
});

function openLightbox(src) {
  const lightbox = document.getElementById('imageLightbox');
  document.getElementById('lightboxImg').src = src;
  lightbox.style.display = 'flex';
}

function closeLightbox() {
  const lightbox = document.getElementById('imageLightbox');
  if (!lightbox || lightbox.style.display !== 'flex') return;
  lightbox.style.display = 'none';
  document.getElementById('lightboxImg').src = '';
}

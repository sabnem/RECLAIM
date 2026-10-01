// WebSocket setup for real-time messaging
const conversationId = inboxConfig.conversationId;
const currentUserId = inboxConfig.userId;
const recipientId = inboxConfig.recipientId;
const itemId = inboxConfig.itemId;

// WebSocket connection
const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
const wsUrl = protocol + window.location.host + '/ws/chat/' + conversationId + '/';
const chatSocket = new WebSocket(wsUrl);

chatSocket.onopen = function(e) {
  };

chatSocket.onmessage = function(e) {
  const data = JSON.parse(e.data);

  // Handle typing notifications
  if (data.type === 'typing') {
    if (data.sender_id != currentUserId) {
      const typingEl = document.getElementById('typingIndicator');
      if (data.is_typing) {
        typingEl.textContent = data.sender_username + ' is typing...';
        typingEl.style.display = 'block';
      } else {
        typingEl.style.display = 'none';
      }
    }
    return;
  }

  // Handle regular messages, edits and deletions
  if (data.type === 'message') {
    appendMessage(data);
    return;
  }
  if (data.type === 'message_edited') {
    const el = document.querySelector('[data-message-id="' + data.message_id + '"]');
    if (el) {
      const contentEl = el.querySelector('.message-content');
      if (contentEl) {
        contentEl.textContent = data.new_content;
        // add edited tag
        let editedTag = el.querySelector('.edited-tag');
        if (!editedTag) {
          editedTag = document.createElement('small');
          editedTag.className = 'text-muted edited-tag';
          editedTag.textContent = ' (edited)';
          contentEl.appendChild(editedTag);
        }
      }
    }
    return;
  }
  if (data.type === 'message_deleted') {
    const el = document.querySelector('[data-message-id="' + data.message_id + '"]');
    if (!el) return;
    if (data.for_everyone) {
      // replace content with placeholder
      const contentEl = el.querySelector('.message-content');
      if (contentEl) {
        contentEl.textContent = 'This message was deleted';
      } else {
        const newC = document.createElement('div');
        newC.className = 'mb-1 message-content';
        newC.textContent = 'This message was deleted';
        el.insertBefore(newC, el.querySelector('.small'));
      }
      // Replace action buttons with a "Remove from view" option so users can delete the placeholder for themselves
      const actions = el.querySelector('.message-actions');
      if (actions) {
        // Clear existing actions and provide a single "Delete for me" entry
        actions.innerHTML = `\n            <button class="btn btn-link p-0 text-white" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>\n            <ul class="dropdown-menu">\n              <li><a href="#" class="dropdown-item delete-for-me-btn">Delete for me</a></li>\n            </ul>`;
        // Attach handler
        const delMe = actions.querySelector('.delete-for-me-btn');
        if (delMe) {
          delMe.addEventListener('click', function(ev) {
            ev.preventDefault();
            if (confirm('Remove this deleted message from your view?')) {
              sendDelete(data.message_id, false);
            }
          });
        }
      }
    } else {
      // delete for me: only remove for requesting user
      if (parseInt(data.requesting_user_id) === parseInt(currentUserId)) {
        const wrapper = el.parentElement; // outer d-flex
        if (wrapper) wrapper.remove();
      }
    }
    return;
  }
};

chatSocket.onclose = function(e) {
  console.error('❌ WebSocket closed unexpectedly', e);
};

chatSocket.onerror = function(e) {
  console.error('❌ WebSocket error:', e);
};

// Function to append message to chat
function appendMessage(data) {
  const chatHistory = document.getElementById('chatHistory');
  const isCurrentUser = data.sender_id == currentUserId;

  // Avoid duplicating if message already present
  if (data.message_id) {
    const existing = document.querySelector('[data-message-id="' + data.message_id + '"]');
    if (existing) return;
  }

  const messageDiv = document.createElement('div');
  messageDiv.className = 'd-flex mb-3 ' + (isCurrentUser ? 'justify-content-end' : 'justify-content-start');

  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = 'chat-bubble ' + (isCurrentUser ? 'sent' : 'received');
  if (data.message_id) bubbleDiv.setAttribute('data-message-id', data.message_id);

  // Content or deleted placeholder
  if (data.deleted_for_everyone) {
    const del = document.createElement('div');
    del.className = 'mb-1 message-content';
    del.textContent = 'This message was deleted';
    bubbleDiv.appendChild(del);
  } else {
    if (data.image) {
      const imgWrap = document.createElement('div');
      imgWrap.className = 'mb-2';
      const img = document.createElement('img');
      img.className = 'img-fluid';
      img.src = data.image;
      img.onclick = function() { openLightbox(data.image); };
      imgWrap.appendChild(img);
      bubbleDiv.appendChild(imgWrap);
    }
    if (data.message) {
      const contentDiv = document.createElement('div');
      contentDiv.className = 'mb-1 message-content';
      contentDiv.textContent = data.message;
      bubbleDiv.appendChild(contentDiv);
    }
  }

  const timeDiv = document.createElement('div');
  timeDiv.className = 'small opacity-75 text-end mt-1';
  if (data.timestamp) {
    timeDiv.textContent = data.timestamp;
  } else {
    const now = new Date();
    timeDiv.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  bubbleDiv.appendChild(timeDiv);

  // Actions dropdown
  const actionsWrapper = document.createElement('div');
  actionsWrapper.className = 'message-actions dropdown';
  actionsWrapper.style.position = 'absolute';
  actionsWrapper.style.top = '6px';
  if (isCurrentUser) actionsWrapper.style.right = '6px'; else actionsWrapper.style.left = '6px';
  // If this message was deleted for everyone, only provide the "Delete for me" option
  if (data.deleted_for_everyone) {
    actionsWrapper.innerHTML = `\n        <button class="btn btn-link p-0 text-white" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>\n        <ul class="dropdown-menu ${isCurrentUser ? 'dropdown-menu-end' : ''}">\n          <li><a href="#" class="dropdown-item delete-for-me-btn">Delete for me</a></li>\n        </ul>\n      `;
  } else {
    actionsWrapper.innerHTML = `\n        <button class="btn btn-link p-0 text-white" data-bs-toggle="dropdown"><i class="bi bi-three-dots-vertical"></i></button>\n        <ul class="dropdown-menu ${isCurrentUser ? 'dropdown-menu-end' : ''}">\n          ${isCurrentUser ? '<li><a href="#" class="dropdown-item edit-message-btn">Edit</a></li>' : ''}\n          <li><a href="#" class="dropdown-item delete-for-me-btn">Delete for me</a></li>\n          ${isCurrentUser ? '<li><a href="#" class="dropdown-item text-danger delete-for-everyone-btn">Delete for everyone</a></li>' : ''}\n        </ul>\n      `;
  }
  bubbleDiv.appendChild(actionsWrapper);

  messageDiv.appendChild(bubbleDiv);
  chatHistory.appendChild(messageDiv);

  // Attach event handlers for actions
  const editBtn = bubbleDiv.querySelector('.edit-message-btn');
  if (editBtn) {
    editBtn.addEventListener('click', function(ev) {
      ev.preventDefault();
      openEditInline(bubbleDiv, data.message_id);
    });
  }
  const delMeBtn = bubbleDiv.querySelector('.delete-for-me-btn');
  if (delMeBtn) {
    delMeBtn.addEventListener('click', function(ev) {
      ev.preventDefault();
      if (confirm('Delete this message for you?')) {
        sendDelete(data.message_id, false);
      }
    });
  }
  const delAllBtn = bubbleDiv.querySelector('.delete-for-everyone-btn');
  if (delAllBtn) {
    delAllBtn.addEventListener('click', function(ev) {
      ev.preventDefault();
      if (confirm('Delete this message for everyone? This cannot be undone.')) {
        sendDelete(data.message_id, true);
      }
    });
  }

  // Scroll to bottom
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Handle form submission
const chatForm = document.getElementById('chatForm');
const messageInput = chatForm.querySelector('[name="message"]');

// Typing indicator handling
let typingTimeout = null;
function sendTyping(isTyping) {
  if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) return;
  const payload = {
    type: 'typing',
    sender_id: currentUserId,
    sender_username: inboxConfig.username,
    is_typing: isTyping,
  };
  try {
    chatSocket.send(JSON.stringify(payload));
  } catch (err) {
    console.error('Typing send error', err);
  }
}

chatForm.addEventListener('submit', function(e) {
  e.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;

  // Send message via WebSocket (server will broadcast authoritative message)
  const messageData = {
    type: 'message',
    'message': message,
    'sender_id': currentUserId,
    'recipient_id': recipientId,
    'item_id': itemId,
    'image': null
  };
  chatSocket.send(JSON.stringify(messageData));

  // Clear input and stop typing
  messageInput.value = '';
  sendTyping(false);
});

// Send edit over WebSocket
function sendEdit(messageId, newContent) {
  if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) return;
  const payload = {
    type: 'edit',
    message_id: messageId,
    sender_id: currentUserId,
    new_content: newContent
  };
  chatSocket.send(JSON.stringify(payload));
}

// Send delete over WebSocket
function sendDelete(messageId, forEveryone) {
  // Debug logging so we can trace delete attempts in the browser console
  if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
    console.warn('WebSocket not open; attempting HTTP fallback to delete view');
    // Fallback: POST to HTTP endpoint for delete
    const csrfInput = document.querySelector('#chatForm input[name="csrfmiddlewaretoken"]');
    const csrfToken = csrfInput ? csrfInput.value : null;
    fetch(inboxConfig.deleteUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ message_id: messageId, for_everyone: forEveryone })
    })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        // If delete for me, remove the DOM for current user; if for everyone broadcast will handle others
        if (!forEveryone) {
          const el = document.querySelector('[data-message-id="' + messageId + '"]');
          if (el) {
            const wrapper = el.parentElement; if (wrapper) wrapper.remove();
          }
        } else {
          // for everyone: emulate server broadcast for current user
          const el = document.querySelector('[data-message-id="' + messageId + '"]');
          if (el) {
            const contentEl = el.querySelector('.message-content');
            if (contentEl) contentEl.textContent = 'This message was deleted';
          }
        }
      } else {
        alert('Failed to delete message: ' + (data.error || 'unknown'));
      }
    })
    .catch(err => {
      console.error('HTTP delete fallback failed', err);
      alert('Could not delete message. Try again.');
    });
    return;
  }
  const payload = {
    type: 'delete',
    message_id: messageId,
    sender_id: currentUserId,
    for_everyone: forEveryone
  };
  try {
    chatSocket.send(JSON.stringify(payload));
    } catch (err) {
    console.error('Failed to send delete via WebSocket', err, payload);
    // Try HTTP fallback if WS send throws
    const csrfInput = document.querySelector('#chatForm input[name="csrfmiddlewaretoken"]');
    const csrfToken = csrfInput ? csrfInput.value : null;
    fetch(inboxConfig.deleteUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ message_id: messageId, for_everyone: forEveryone })
    })
    .then(r => r.json())
    .then(data => { })
    .catch(err2 => console.error('HTTP fallback after WS error failed', err2));
  }
}

// Inline edit UI
function openEditInline(bubbleEl, messageId) {
  const contentEl = bubbleEl.querySelector('.message-content');
  if (!contentEl) return;
  const original = contentEl.textContent;
  const textarea = document.createElement('textarea');
  textarea.className = 'form-control mb-2';
  textarea.value = original;
  bubbleEl.insertBefore(textarea, contentEl);
  contentEl.style.display = 'none';

  const saveBtn = document.createElement('button');
  saveBtn.className = 'btn btn-sm btn-primary me-2';
  saveBtn.textContent = 'Save';
  const cancelBtn = document.createElement('button');
  cancelBtn.className = 'btn btn-sm btn-secondary';
  cancelBtn.textContent = 'Cancel';
  const ctrl = document.createElement('div');
  ctrl.className = 'mt-2';
  ctrl.appendChild(saveBtn);
  ctrl.appendChild(cancelBtn);
  bubbleEl.insertBefore(ctrl, bubbleEl.querySelector('.small'));

  saveBtn.addEventListener('click', function(ev) {
    ev.preventDefault();
    const newText = textarea.value.trim();
    if (!newText) return alert('Message cannot be empty');
    // Send edit
    sendEdit(messageId, newText);
    // Tear down UI
    contentEl.textContent = newText + ' ';
    const tag = document.createElement('small'); tag.className='text-muted edited-tag'; tag.textContent=' (edited)'; contentEl.appendChild(tag);
    contentEl.style.display = '';
    textarea.remove(); ctrl.remove();
  });
  cancelBtn.addEventListener('click', function(ev) {
    ev.preventDefault();
    contentEl.style.display = '';
    textarea.remove(); ctrl.remove();
  });
}

if (messageInput) {
  messageInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      chatForm.requestSubmit();
    }
    // Send typing true on any key press and debounce stop
    sendTyping(true);
    if (typingTimeout) clearTimeout(typingTimeout);
    typingTimeout = setTimeout(function() { sendTyping(false); }, 1400);
  });
}

// Attach handlers to initial page-loaded messages
function attachMessageHandlers() {
  document.querySelectorAll('.edit-message-btn').forEach(btn => {
    btn.removeEventListener('click', handleEditClick);
    btn.addEventListener('click', handleEditClick);
  });
  document.querySelectorAll('.delete-for-me-btn').forEach(btn => {
    btn.removeEventListener('click', handleDeleteForMeClick);
    btn.addEventListener('click', handleDeleteForMeClick);
  });
  document.querySelectorAll('.delete-for-everyone-btn').forEach(btn => {
    btn.removeEventListener('click', handleDeleteForEveryoneClick);
    btn.addEventListener('click', handleDeleteForEveryoneClick);
  });
}

// Event handlers
function handleEditClick(e) {
  e.preventDefault();
  const messageId = this.getAttribute('data-message-id');
  const bubbleEl = this.closest('.chat-bubble');
  openEditInline(bubbleEl, messageId);
}

function handleDeleteForMeClick(e) {
  e.preventDefault();
  const messageId = this.getAttribute('data-message-id');
  if (confirm('Delete this message for you?')) {
    sendDelete(messageId, false);
  }
}

function handleDeleteForEveryoneClick(e) {
  e.preventDefault();
  const messageId = this.getAttribute('data-message-id');
  if (confirm('Delete this message for everyone? This cannot be undone.')) {
    sendDelete(messageId, true);
  }
}

// Attach handlers on page load
attachMessageHandlers();

const inboxConfig = document.getElementById('inboxConfig').dataset;

document.addEventListener("DOMContentLoaded", function() {
  const conversationList = document.getElementById('conversationList');
  const chatArea = document.getElementById('chatArea');
  const backToListBtn = document.getElementById('backToListBtn');
  const mobileQuery = window.matchMedia('(max-width: 767.98px)');
  let showChat = (inboxConfig.hasConversation === 'true');
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
    document.getElementById('toggleArchivedBtn')?.focus();
  });
  mobileQuery.addEventListener('change', initMobileView);
  window.visualViewport?.addEventListener('resize', updateViewportHeight);
  initMobileView();

  // Scroll chat to bottom
  let chatHistory = document.getElementById("chatHistory");
  if (chatHistory) chatHistory.scrollTop = chatHistory.scrollHeight;

  // Image upload preview
  const fileInput = document.getElementById("chatImageUpload");
  const previewContainer = document.getElementById("imagePreviewContainer");
  const previewImg = document.getElementById("chatImagePreview");
  const removeBtn = document.getElementById("removeImageBtn");

  if (fileInput) {
    fileInput.addEventListener("change", function() {
      if (this.files && this.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
          previewImg.src = e.target.result;
          previewContainer.style.display = "block";
        };
        reader.readAsDataURL(this.files[0]);
      }
    });
  }

  if (removeBtn) {
    removeBtn.addEventListener("click", function() {
      fileInput.value = "";
      previewImg.src = "";
      previewContainer.style.display = "none";
    });
  }

  // Archive conversation functionality
  const archiveConversationBtn = document.getElementById('archiveConversationBtn');
  if (archiveConversationBtn) {
    archiveConversationBtn.addEventListener('click', function(e) {
      e.preventDefault();

      if (confirm('Archive this conversation? Messages will be hidden from your inbox but preserved for reference.')) {
        // Send request to backend to archive messages
        fetch(inboxConfig.clearUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': inboxConfig.csrfToken
          },
          body: JSON.stringify({
            action: 'archive',
            item_id: inboxConfig.itemId,
            recipient_id: inboxConfig.recipientId
          })
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            // Show success message
            alert('✅ Conversation archived successfully! Messages are preserved for reference.');

            // Redirect to inbox home
            window.location.href = inboxConfig.inboxUrl + '?view=list';
          } else {
            alert('Failed to archive conversation: ' + data.error);
          }
        })
        .catch(error => {
          console.error('Error:', error);
          alert('An error occurred while archiving the conversation.');
        });
      }
    });
  }

  // Unarchive conversation functionality
  const unarchiveConversationBtn = document.getElementById('unarchiveConversationBtn');
  if (unarchiveConversationBtn) {
    unarchiveConversationBtn.addEventListener('click', function(e) {
      e.preventDefault();

      if (confirm('Unarchive this conversation? Messages will be restored to your inbox.')) {
        // Send request to backend to unarchive messages
        fetch(inboxConfig.clearUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': inboxConfig.csrfToken
          },
          body: JSON.stringify({
            action: 'unarchive',
            item_id: inboxConfig.itemId,
            recipient_id: inboxConfig.recipientId
          })
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            // Show success message
            alert('✅ Conversation unarchived successfully! Messages are now visible in your inbox.');

            // Redirect to active inbox
            window.location.href = inboxConfig.inboxUrl + '?view=list';
          } else {
            alert('Failed to unarchive conversation: ' + data.error);
          }
        })
        .catch(error => {
          console.error('Error:', error);
          alert('An error occurred while unarchiving the conversation.');
        });
      }
    });
  }

  // Delete conversation functionality
  const clearConversationBtn = document.getElementById('clearConversationBtn');
  if (clearConversationBtn) {
    clearConversationBtn.addEventListener('click', function(e) {
      e.preventDefault();

      if (confirm('Are you sure you want to delete this conversation? This action cannot be undone and all messages will be permanently removed.')) {
        // Send request to backend to delete messages
        fetch(inboxConfig.clearUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': inboxConfig.csrfToken
          },
          body: JSON.stringify({
            action: 'delete',
            item_id: inboxConfig.itemId,
            recipient_id: inboxConfig.recipientId
          })
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            // Show success message
            alert('✅ Conversation deleted successfully! All messages have been permanently removed.');

            // Redirect to inbox home
            window.location.href = inboxConfig.inboxUrl + '?view=list';
          } else {
            alert('Failed to delete conversation: ' + data.error);
          }
        })
        .catch(error => {
          console.error('Error:', error);
          alert('An error occurred while deleting the conversation.');
        });
      }
    });
  }

  // Toggle between active and archived conversations
  const toggleArchivedBtn = document.getElementById('toggleArchivedBtn');
  if (toggleArchivedBtn) {
    toggleArchivedBtn.addEventListener('click', function(e) {
      e.preventDefault();
      const currentUrl = new URL(window.location);
      const isArchived = currentUrl.searchParams.get('archived') === '1';

      if (isArchived) {
        // Switch to active conversations
        currentUrl.searchParams.delete('archived');
        currentUrl.searchParams.set('view', 'list');
      } else {
        // Switch to archived conversations
        currentUrl.searchParams.set('archived', '1');
        currentUrl.searchParams.delete('view');
        currentUrl.searchParams.delete('item_id');
        currentUrl.searchParams.delete('recipient_id');
      }

      window.location.href = currentUrl.toString();
    });
  }

});

// Lightbox functions
function openLightbox(src) {
  const lightbox = document.getElementById('imageLightbox');
  const lightboxImg = document.getElementById('lightboxImg');
  lightboxImg.src = src;
  lightbox.style.display = 'flex';
}

function closeLightbox() {
  const lightbox = document.getElementById('imageLightbox');
  const lightboxImg = document.getElementById('lightboxImg');
  lightbox.style.display = 'none';
  lightboxImg.src = '';
}

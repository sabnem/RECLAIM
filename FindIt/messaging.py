"""Chat visibility rules and real-time delivery shared by views and the WebSocket consumer.

Every member has a private view of a conversation (WhatsApp semantics): deleting a
message "for me", clearing, deleting or archiving a chat never changes what the other
participant sees. Only "delete for everyone" by the sender affects both sides.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import ConversationState, Message

logger = logging.getLogger(__name__)

TYPING_TTL_SECONDS = 6
SYNC_MESSAGE_LIMIT = 300


def user_group(user_id):
    return f'user_{user_id}'


def typing_cache_key(item_id, sender_id, recipient_id):
    return f'chat-typing:{item_id}:{sender_id}:{recipient_id}'


def conversation_messages(item_id, user_id, other_id):
    """Every message between two members about one item, regardless of who deleted what."""
    return Message.objects.filter(item_id=item_id).filter(
        Q(sender_id=user_id, recipient_id=other_id) | Q(sender_id=other_id, recipient_id=user_id)
    )


def hidden_for_user(user_id):
    return Q(sender_id=user_id, deleted_by_sender=True) | Q(recipient_id=user_id, deleted_by_recipient=True)


def get_state(user_id, item_id, other_id):
    return ConversationState.objects.filter(user_id=user_id, item_id=item_id, other_user_id=other_id).first()


def visible_messages(user_id, item_id, other_id, state=None):
    messages = conversation_messages(item_id, user_id, other_id).exclude(hidden_for_user(user_id))
    if state and state.cleared_at:
        messages = messages.filter(timestamp__gt=state.cleared_at)
    return messages.select_related('sender').order_by('timestamp', 'id')


def avatar_url(user):
    profile = getattr(user, 'userprofile', None)
    try:
        return profile.profile_picture.url if profile and profile.profile_picture else ''
    except Exception:  # Missing remote media must not break chat rendering.
        return ''


def display_name(user):
    return user.get_full_name() or user.username


def preview_text(message, viewer_id):
    if message.deleted_for_everyone:
        return 'You deleted this message' if message.sender_id == viewer_id else 'This message was deleted'
    if message.content:
        return message.content
    return 'Photo' if message.image else ''


def serialize_message(message):
    image = ''
    if message.image and not message.deleted_for_everyone:
        try:
            image = message.image.url
        except Exception:
            image = ''
    return {
        'id': message.id,
        'item_id': message.item_id,
        'item_title': message.item.title,
        'sender_id': message.sender_id,
        'sender_name': display_name(message.sender),
        'sender_avatar': avatar_url(message.sender),
        'recipient_id': message.recipient_id,
        'content': '' if message.deleted_for_everyone else message.content,
        'image': image,
        'timestamp': message.timestamp.isoformat(),
        'edited': message.edited,
        'deleted_for_everyone': message.deleted_for_everyone,
        'is_read': message.is_read,
    }


def broadcast(user_ids, payload):
    """Push an event to each member's open inbox tabs after the transaction commits.

    Delivery is best effort: messages are already stored, and clients re-sync over
    HTTP, so a missing or unavailable channel layer must never fail the request.
    """
    def send():
        layer = get_channel_layer()
        if layer is None:
            return
        for user_id in set(user_ids):
            try:
                async_to_sync(layer.group_send)(user_group(user_id), {'type': 'chat.event', 'payload': payload})
            except Exception:
                logger.warning('Chat event delivery failed for user %s', user_id, exc_info=True)

    transaction.on_commit(send)


def mark_conversation_read(user, item_id, other_id):
    """Mark incoming messages read and send blue ticks to the sender."""
    unread = conversation_messages(item_id, user.id, other_id).filter(recipient_id=user.id, is_read=False)
    message_ids = list(unread.values_list('id', flat=True))
    if message_ids:
        Message.objects.filter(id__in=message_ids).update(is_read=True)
        broadcast([other_id, user.id], {
            'type': 'read', 'item_id': int(item_id), 'reader_id': user.id,
            'sender_id': int(other_id), 'message_ids': message_ids,
        })
    return len(message_ids)


def set_typing(sender_id, item_id, recipient_id, is_typing):
    key = typing_cache_key(item_id, sender_id, recipient_id)
    if is_typing:
        cache.set(key, True, TYPING_TTL_SECONDS)
    else:
        cache.delete(key)


def is_typing(sender_id, item_id, recipient_id):
    return bool(cache.get(typing_cache_key(item_id, sender_id, recipient_id)))


def update_state(user, item_id, other_id, **fields):
    state, _ = ConversationState.objects.update_or_create(
        user=user, item_id=item_id, other_user_id=other_id, defaults=fields,
    )
    return state


def clear_for_user(user, item_id, other_id, hide):
    """Clear (keep in list) or delete (remove from list) a chat for this member only."""
    now = timezone.now()
    conversation_messages(item_id, user.id, other_id).filter(recipient_id=user.id, is_read=False).update(is_read=True)
    return update_state(user, item_id, other_id, cleared_at=now, hidden=hide, **({'archived': False} if hide else {}))

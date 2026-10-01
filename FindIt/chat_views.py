"""Inbox and chat endpoints with per-member deletion, read receipts and typing state."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import messaging
from .models import ConversationState, Item, Message

MAX_MESSAGE_LENGTH = 4000
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class ChatRequestError(Exception):
    def __init__(self, error, status=400):
        super().__init__(error)
        self.error = error
        self.status = status


def _error(error, status=400):
    return JsonResponse({'success': False, 'error': error}, status=status)


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ChatRequestError('Invalid JSON')


def _conversation_ids(user, data):
    """Validate the (item, other member) pair a request refers to."""
    try:
        item_id, other_id = int(data.get('item_id')), int(data.get('recipient_id'))
    except (TypeError, ValueError):
        raise ChatRequestError('Missing item_id or recipient_id')
    if other_id == user.id:
        raise ChatRequestError('You cannot message yourself')
    if not Item.objects.filter(pk=item_id).exists() or not User.objects.filter(pk=other_id).exists():
        raise ChatRequestError('Conversation not found', 404)
    return item_id, other_id


def _get_message(data):
    try:
        return Message.objects.select_related('item', 'sender__userprofile').get(pk=int(data.get('message_id')))
    except (TypeError, ValueError):
        raise ChatRequestError('Missing message_id')
    except Message.DoesNotExist:
        raise ChatRequestError('Message not found', 404)


def chat_endpoint(view):
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except ChatRequestError as exc:
            return _error(exc.error, exc.status)
    wrapped.__name__ = view.__name__
    wrapped.__doc__ = view.__doc__
    return wrapped


def create_message(sender, recipient_id, item_id, content, image=None):
    content = (content or '').strip()
    if not content and not image:
        raise ChatRequestError('Message is empty')
    if len(content) > MAX_MESSAGE_LENGTH:
        raise ChatRequestError(f'Messages are limited to {MAX_MESSAGE_LENGTH} characters')
    if image is not None:
        if not (image.content_type or '').startswith('image/'):
            raise ChatRequestError('Only image attachments are supported')
        if image.size > MAX_IMAGE_BYTES:
            raise ChatRequestError('Images must be 10 MB or smaller')
    message = Message.objects.create(
        sender=sender, recipient_id=recipient_id, item_id=item_id, content=content, image=image,
    )
    message = Message.objects.select_related('item', 'sender__userprofile').get(pk=message.pk)
    messaging.set_typing(sender.id, item_id, recipient_id, False)
    messaging.broadcast([sender.id, recipient_id], {'type': 'message', 'message': messaging.serialize_message(message)})
    return message


def build_conversation_list(user, archived):
    states = {(s.item_id, s.other_user_id): s for s in ConversationState.objects.filter(user=user)}
    rows = (
        Message.objects.filter(Q(sender=user) | Q(recipient=user))
        .exclude(messaging.hidden_for_user(user.id))
        .select_related('item', 'sender__userprofile', 'recipient__userprofile')
        .order_by('-timestamp', '-id')
    )
    conversations = {}
    for msg in rows:
        other = msg.recipient if msg.sender_id == user.id else msg.sender
        key = (msg.item_id, other.id)
        state = states.get(key)
        if state and state.cleared_at and msg.timestamp <= state.cleared_at:
            continue
        if bool(state and state.archived) != archived:
            continue
        convo = conversations.get(key)
        if convo is None:
            convo = conversations[key] = _conversation_row(user, msg.item, other)
            convo.update({
                'last_id': msg.id,
                'last_message': messaging.preview_text(msg, user.id),
                'last_date': msg.timestamp,
                'last_is_mine': msg.sender_id == user.id,
                'last_is_read': msg.is_read,
                'last_is_deleted': msg.deleted_for_everyone,
            })
        if msg.recipient_id == user.id and not msg.is_read:
            convo['unread'] += 1

    # Cleared chats stay listed (empty) until the member deletes them.
    empty_states = ConversationState.objects.filter(
        user=user, archived=archived, hidden=False, cleared_at__isnull=False,
    ).select_related('item', 'other_user__userprofile')
    for state in empty_states:
        key = (state.item_id, state.other_user_id)
        if key not in conversations:
            row = conversations[key] = _conversation_row(user, state.item, state.other_user)
            row['last_date'] = state.cleared_at

    return sorted(conversations.values(), key=lambda row: row['last_date'], reverse=True)


def _conversation_row(user, item, other):
    return {
        'key': f'{item.id}-{other.id}',
        'item_id': item.id,
        'other_user_id': other.id,
        'name': messaging.display_name(other),
        'avatar_url': messaging.avatar_url(other),
        'item_title': item.title,
        'item_image': _photo_url(item),
        'last_id': '',
        'last_message': '',
        'last_date': None,
        'last_is_mine': False,
        'last_is_read': False,
        'last_is_deleted': False,
        'unread': 0,
    }


def _photo_url(item):
    try:
        return item.photo.url if item.photo else ''
    except Exception:
        return ''


@never_cache
@login_required
def inbox(request):
    item_id = request.GET.get('item_id')
    recipient_id = request.GET.get('recipient_id')
    show_archived = request.GET.get('archived') == '1'

    # Non-JavaScript fallback for the chat form.
    if request.method == 'POST':
        try:
            post_item_id, post_recipient_id = _conversation_ids(request.user, request.POST)
            create_message(request.user, post_recipient_id, post_item_id,
                           request.POST.get('message'), request.FILES.get('chat_image'))
        except ChatRequestError as exc:
            messages.error(request, exc.error)
            return redirect('inbox')
        return redirect(f"{reverse('inbox')}?item_id={post_item_id}&recipient_id={post_recipient_id}")

    conversations = build_conversation_list(request.user, show_archived)

    active = None
    if item_id and recipient_id:
        try:
            active_item_id, active_other_id = _conversation_ids(request.user, request.GET)
        except ChatRequestError as exc:
            messages.error(request, exc.error)
            return redirect('inbox')
        active = _active_conversation(request.user, active_item_id, active_other_id)
    elif conversations and request.GET.get('view') != 'list':
        first = conversations[0]
        active = _active_conversation(request.user, first['item_id'], first['other_user_id'])

    if active:
        messaging.mark_conversation_read(request.user, active['item_id'], active['recipient_id'])
        for row in conversations:
            if row['key'] == active['key']:
                row['unread'] = 0

    return render(request, 'FindIt/inbox.html', {
        'conversations': conversations,
        'active_conversation': active,
        'show_archived': show_archived,
    })


def _active_conversation(user, item_id, other_id):
    item = Item.objects.get(pk=item_id)
    other = User.objects.select_related('userprofile').get(pk=other_id)
    state = messaging.get_state(user.id, item_id, other_id)
    history = messaging.visible_messages(user.id, item_id, other_id, state).select_related('item', 'sender__userprofile')
    return {
        'key': f'{item_id}-{other_id}',
        'item_id': item_id,
        'recipient_id': other_id,
        'name': messaging.display_name(other),
        'avatar_url': messaging.avatar_url(other),
        'item_title': item.title,
        'item_image': _photo_url(item),
        'archived': bool(state and state.archived),
        'messages': [messaging.serialize_message(msg) for msg in history],
    }


@login_required
@require_POST
@chat_endpoint
def send_chat_message(request):
    item_id, recipient_id = _conversation_ids(request.user, request.POST)
    message = create_message(request.user, recipient_id, item_id,
                             request.POST.get('message'), request.FILES.get('chat_image'))
    return JsonResponse({'success': True, 'message': messaging.serialize_message(message)})


@login_required
@require_POST
@chat_endpoint
def edit_message(request):
    payload = _json_body(request)
    msg = _get_message(payload)
    new_content = (payload.get('new_content') or '').strip()
    if msg.sender_id != request.user.id:
        return _error('Permission denied', 403)
    if msg.deleted_for_everyone:
        return _error('Deleted messages cannot be edited')
    if not new_content:
        return _error('Message cannot be empty')
    if len(new_content) > MAX_MESSAGE_LENGTH:
        return _error(f'Messages are limited to {MAX_MESSAGE_LENGTH} characters')
    msg.content = new_content
    msg.edited = True
    msg.edited_at = timezone.now()
    msg.save(update_fields=['content', 'edited', 'edited_at'])
    data = messaging.serialize_message(msg)
    messaging.broadcast([msg.sender_id, msg.recipient_id], {'type': 'message_updated', 'message': data})
    return JsonResponse({'success': True, 'message_id': msg.id, 'new_content': msg.content, 'message': data})


@login_required
@require_POST
@chat_endpoint
def delete_message(request):
    payload = _json_body(request)
    msg = _get_message(payload)
    if request.user.id not in (msg.sender_id, msg.recipient_id):
        return _error('Permission denied', 403)

    if payload.get('for_everyone'):
        if msg.sender_id != request.user.id:
            return _error('Permission denied', 403)
        if not msg.deleted_for_everyone:
            # Wipe the stored content so the recipient can no longer retrieve it.
            msg.deleted_for_everyone = True
            msg.deleted_at = timezone.now()
            msg.deleted_by = request.user
            msg.content = ''
            msg.image = None
            msg.save(update_fields=['deleted_for_everyone', 'deleted_at', 'deleted_by', 'content', 'image'])
        data = messaging.serialize_message(msg)
        messaging.broadcast([msg.sender_id, msg.recipient_id], {'type': 'message_updated', 'message': data})
        return JsonResponse({'success': True, 'message_id': msg.id, 'for_everyone': True, 'message': data})

    if msg.sender_id == request.user.id:
        msg.deleted_by_sender = True
    if msg.recipient_id == request.user.id:
        msg.deleted_by_recipient = True
    msg.save(update_fields=['deleted_by_sender', 'deleted_by_recipient'])
    # Only the requester's own tabs are told; the other member keeps the message.
    messaging.broadcast([request.user.id], {'type': 'message_hidden', 'message_id': msg.id})
    return JsonResponse({'success': True, 'message_id': msg.id, 'for_everyone': False})


@login_required
@require_POST
@chat_endpoint
def mark_read(request):
    item_id, other_id = _conversation_ids(request.user, _json_body(request))
    return JsonResponse({'success': True, 'marked': messaging.mark_conversation_read(request.user, item_id, other_id)})


@never_cache
@login_required
@require_GET
@chat_endpoint
def sync_conversation(request):
    """Polling fallback used while the WebSocket is unavailable."""
    item_id, other_id = _conversation_ids(request.user, request.GET)
    state = messaging.get_state(request.user.id, item_id, other_id)
    history = list(
        messaging.visible_messages(request.user.id, item_id, other_id, state)
        .select_related('item', 'sender__userprofile')
        .order_by('-timestamp', '-id')[:messaging.SYNC_MESSAGE_LIMIT]
    )
    history.reverse()
    return JsonResponse({
        'success': True,
        'messages': [messaging.serialize_message(msg) for msg in history],
        'typing': messaging.is_typing(other_id, item_id, request.user.id),
    })


@login_required
@require_POST
@chat_endpoint
def typing_status(request):
    """HTTP twin of the WebSocket typing event for clients without a socket."""
    payload = _json_body(request)
    item_id, other_id = _conversation_ids(request.user, payload)
    is_typing = bool(payload.get('is_typing'))
    messaging.set_typing(request.user.id, item_id, other_id, is_typing)
    messaging.broadcast([other_id], {'type': 'typing', 'item_id': item_id, 'sender_id': request.user.id, 'is_typing': is_typing})
    return JsonResponse({'success': True})


@login_required
@require_POST
@chat_endpoint
def conversation_action(request):
    """Archive, unarchive, clear or delete a chat for the requesting member only."""
    payload = _json_body(request)
    item_id, other_id = _conversation_ids(request.user, payload)
    action = payload.get('action')
    if action == 'archive':
        messaging.update_state(request.user, item_id, other_id, archived=True)
        message = 'Chat archived'
    elif action == 'unarchive':
        messaging.update_state(request.user, item_id, other_id, archived=False)
        message = 'Chat unarchived'
    elif action == 'clear':
        messaging.clear_for_user(request.user, item_id, other_id, hide=False)
        message = 'Chat cleared'
    elif action == 'delete':
        messaging.clear_for_user(request.user, item_id, other_id, hide=True)
        message = 'Chat deleted'
    else:
        return _error('Invalid action')
    messaging.broadcast([request.user.id], {'type': 'conversation', 'action': action, 'item_id': item_id, 'other_user_id': other_id})
    return JsonResponse({'success': True, 'action': action, 'message': message})


@login_required
def send_message(request, item_id, recipient_id):
    """Legacy chat URL; conversations now live in the inbox."""
    return redirect(f"{reverse('inbox')}?item_id={item_id}&recipient_id={recipient_id}")

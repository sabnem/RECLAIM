import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from . import messaging

logger = logging.getLogger(__name__)


class InboxConsumer(AsyncJsonWebsocketConsumer):
    """One authenticated socket per member tab.

    Messages, edits, deletions and read receipts are saved over HTTP and pushed to
    each participant's personal group; the socket itself only relays typing state.
    The member is always taken from the session, never from client-supplied ids.
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.user = user
        self.group_name = messaging.user_group(user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get('type')
        if kind == 'ping':
            await self.send_json({'type': 'pong'})
            return
        if kind != 'typing':
            return
        try:
            item_id, recipient_id = int(content.get('item_id')), int(content.get('recipient_id'))
        except (TypeError, ValueError):
            return
        if recipient_id == self.user.id:
            return
        is_typing = bool(content.get('is_typing'))
        await database_sync_to_async(messaging.set_typing)(self.user.id, item_id, recipient_id, is_typing)
        await self.channel_layer.group_send(messaging.user_group(recipient_id), {
            'type': 'chat.event',
            'payload': {'type': 'typing', 'item_id': item_id, 'sender_id': self.user.id, 'is_typing': is_typing},
        })

    async def chat_event(self, event):
        await self.send_json(event['payload'])

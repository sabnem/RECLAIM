import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Message
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        print(f"🔵 WebSocket CONNECT: conversation_id={self.conversation_id}, room={self.room_group_name}")

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"✅ WebSocket ACCEPTED: {self.channel_name}")

    async def disconnect(self, close_code):
        print(f"🔴 WebSocket DISCONNECT: conversation_id={self.conversation_id}, code={close_code}")
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        print(f"📨 WebSocket RECEIVED: {text_data}")
        text_data_json = json.loads(text_data)
        # Support different payload types from clients (message, typing)
        payload_type = text_data_json.get('type', 'message')

        if payload_type == 'typing':
            # Broadcast typing status to group
            sender_id = text_data_json.get('sender_id')
            sender_username = text_data_json.get('sender_username', '')
            is_typing = text_data_json.get('is_typing', False)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_typing',
                    'sender_id': sender_id,
                    'sender_username': sender_username,
                    'is_typing': is_typing,
                }
            )
            return

        # Edit message
        if payload_type == 'edit':
            message_id = text_data_json.get('message_id')
            new_content = text_data_json.get('new_content', '')
            sender_id = text_data_json.get('sender_id')

            edited = await self.edit_message_db(message_id, sender_id, new_content)
            if edited:
                # Broadcast edited event
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_edited',
                        'message_id': message_id,
                        'new_content': edited['new_content'],
                        'edited_at': edited['edited_at'],
                        'editor_id': sender_id,
                    }
                )
            return

        # Delete message
        if payload_type == 'delete':
            message_id = text_data_json.get('message_id')
            sender_id = text_data_json.get('sender_id')
            for_everyone = bool(text_data_json.get('for_everyone', False))

            deleted = await self.delete_message_db(message_id, sender_id, for_everyone)
            if deleted:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_deleted',
                        'message_id': message_id,
                        'for_everyone': for_everyone,
                        'requesting_user_id': sender_id,
                        'deleted_at': deleted.get('deleted_at')
                    }
                )
            return

        # Default: normal chat message
        message_content = text_data_json['message']
        sender_id = text_data_json['sender_id']
        recipient_id = text_data_json['recipient_id']
        item_id = text_data_json.get('item_id')
        image = text_data_json.get('image', None)

        print(f"📝 Parsed message: sender={sender_id}, recipient={recipient_id}, item={item_id}, content='{message_content}'")

        # Save message to database
        message = await self.save_message(
            sender_id=sender_id,
            recipient_id=recipient_id,
            item_id=item_id,
            content=message_content,
            image=image
        )

        print(f"💾 Message saved to DB: id={message['id']}")

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message_content,
                'sender_id': sender_id,
                'sender_username': message['sender_username'],
                'timestamp': message['timestamp'],
                'message_id': message['id'],
            }
        )

        print(f"📤 Broadcasted to room: {self.room_group_name}")

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        sender_id = event['sender_id']
        sender_username = event['sender_username']
        timestamp = event['timestamp']
        message_id = event['message_id']

        print(f"📡 Sending to WebSocket client: message_id={message_id}, sender={sender_username}")

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': message,
            'sender_id': sender_id,
            'sender_username': sender_username,
            'timestamp': timestamp,
            'message_id': message_id,
        }))

    async def user_typing(self, event):
        # Forward typing events to WebSocket clients
        sender_id = event.get('sender_id')
        sender_username = event.get('sender_username')
        is_typing = event.get('is_typing', False)

        await self.send(text_data=json.dumps({
            'type': 'typing',
            'sender_id': sender_id,
            'sender_username': sender_username,
            'is_typing': is_typing,
        }))

    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': event.get('message_id'),
            'new_content': event.get('new_content'),
            'edited_at': event.get('edited_at'),
            'editor_id': event.get('editor_id'),
        }))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event.get('message_id'),
            'for_everyone': event.get('for_everyone', False),
            'requesting_user_id': event.get('requesting_user_id'),
            'deleted_at': event.get('deleted_at'),
        }))

    @database_sync_to_async
    def save_message(self, sender_id, recipient_id, item_id, content, image=None):
        from .models import Item
        sender = User.objects.get(id=sender_id)
        recipient = User.objects.get(id=recipient_id)
        item = Item.objects.get(id=item_id)
        
        message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            item=item,
            content=content,
        )
        
        if image:
            message.image = image
            message.save()
        
        return {
            'id': message.id,
            'sender_username': sender.username,
            'timestamp': message.timestamp.strftime('%b. %d, %Y, %I:%M %p'),
        }

    @database_sync_to_async
    def edit_message_db(self, message_id, user_id, new_content):
        try:
            msg = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            return None
        # Only sender can edit their message
        if msg.sender.id != int(user_id):
            return None
        msg.content = new_content
        msg.edited = True
        msg.edited_at = timezone.now()
        msg.save()
        return {
            'new_content': msg.content,
            'edited_at': msg.edited_at.strftime('%b. %d, %Y, %I:%M %p') if msg.edited_at else None
        }

    @database_sync_to_async
    def delete_message_db(self, message_id, user_id, for_everyone=False):
        try:
            msg = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            return None
        user_id = int(user_id)
        if for_everyone:
            # Only sender may delete for everyone in this implementation
            if msg.sender.id != user_id:
                return None
            msg.deleted_for_everyone = True
            msg.deleted_at = timezone.now()
            msg.deleted_by = User.objects.get(id=user_id)
            msg.save()
            return {'deleted_at': msg.deleted_at.strftime('%b. %d, %Y, %I:%M %p')}
        else:
            # mark deleted for this user only
            if msg.sender.id == user_id:
                msg.deleted_by_sender = True
            elif msg.recipient.id == user_id:
                msg.deleted_by_recipient = True
            else:
                return None
            msg.save()
            return {'deleted_at': None}

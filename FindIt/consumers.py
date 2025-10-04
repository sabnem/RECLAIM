import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Message

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
            'message': message,
            'sender_id': sender_id,
            'sender_username': sender_username,
            'timestamp': timestamp,
            'message_id': message_id,
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

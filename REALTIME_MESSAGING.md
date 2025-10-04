# Real-Time Messaging Implementation

## Overview
The messaging system now supports real-time message delivery using WebSocket technology. Messages appear instantly without requiring page refreshes.

## Technology Stack
- **Django Channels 4.3.1**: WebSocket support for Django
- **Daphne 4.2.1**: ASGI server for handling WebSocket connections
- **channels-redis 4.3.0**: Channel layer backend (currently using InMemoryChannelLayer for development)

## How It Works

### Backend Components

1. **ASGI Configuration** (`lost_and_found/asgi.py`)
   - Configured ProtocolTypeRouter to handle both HTTP and WebSocket protocols
   - Uses AuthMiddlewareStack for WebSocket authentication
   - Routes WebSocket connections to appropriate consumers

2. **WebSocket Routing** (`FindIt/routing.py`)
   - WebSocket URL pattern: `ws/chat/<conversation_id>/`
   - Maps to ChatConsumer for handling real-time chat

3. **ChatConsumer** (`FindIt/consumers.py`)
   - Handles WebSocket connections, disconnections, and message events
   - Saves messages to database asynchronously
   - Broadcasts messages to all users in the same conversation room
   - Methods:
     - `connect()`: Joins conversation room group
     - `disconnect()`: Leaves room group
     - `receive()`: Receives message from WebSocket, saves to DB, broadcasts
     - `chat_message()`: Sends message to WebSocket client
     - `save_message()`: Async database operation

### Frontend Components

1. **WebSocket Client** (`FindIt/templates/FindIt/inbox.html`)
   - Establishes WebSocket connection when conversation is active
   - Sends messages via WebSocket instead of POST
   - Listens for incoming messages and appends them to chat in real-time
   - Auto-scrolls to bottom on new messages

## Testing Real-Time Messaging

### Prerequisites
1. Make sure the server is running with Daphne:
   ```bash
   python manage.py runserver
   ```
   You should see: "Starting ASGI/Daphne version 4.2.1 development server"

### Test Steps

1. **Open Two Browser Windows**
   - Window 1: Login as User A
   - Window 2: Login as User B (use incognito/private mode)

2. **Start a Conversation**
   - User A: Navigate to an item and click "Contact Finder" or "Contact Owner"
   - This opens the inbox with the conversation

3. **Open Same Conversation in Both Windows**
   - User B: Navigate to inbox and select the same conversation
   - Both users should now see the same conversation

4. **Test Real-Time Messaging**
   - User A: Type a message and click Send
   - User B: Should see the message appear **instantly** without refreshing
   - User B: Reply to the message
   - User A: Should see the reply **instantly**

5. **Verify Features**
   - ✅ Messages appear in real-time
   - ✅ No page refresh needed
   - ✅ Auto-scroll to latest message
   - ✅ Timestamps are accurate
   - ✅ Message bubbles show correct sender/receiver styling

## Configuration

### Development (Current Setup)
```python
# lost_and_found/settings.py
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}
```

### Production (Recommended)
For production, switch to Redis for better performance and multi-server support:

1. **Install Redis Server**
   - Windows: Download from https://github.com/microsoftarchive/redis/releases
   - Linux: `sudo apt-get install redis-server`
   - Mac: `brew install redis`

2. **Update Settings**
   ```python
   # lost_and_found/settings.py
   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {
               "hosts": [('127.0.0.1', 6379)],
           },
       },
   }
   ```

3. **Start Redis**
   ```bash
   redis-server
   ```

## Troubleshooting

### WebSocket Connection Fails
- **Check**: Is Daphne running? Look for "Starting ASGI/Daphne" in console
- **Fix**: Make sure `'daphne'` is first in INSTALLED_APPS

### Messages Not Appearing in Real-Time
- **Check**: Browser console for WebSocket errors (F12 → Console)
- **Check**: Is conversation_id correct in WebSocket URL?
- **Fix**: Verify both users are in the same conversation room

### "No module named 'daphne'" Error
- **Fix**: Install packages in virtual environment:
  ```bash
  pip install channels channels-redis daphne
  ```

### Connection Closes Unexpectedly
- **Check**: Browser console for "WebSocket closed" message
- **Possible causes**:
  - Network issues
  - Server restart
  - Authentication problems
- **Fix**: Page will need to be refreshed to reconnect

## Future Enhancements

### Planned Features
- [ ] Typing indicators ("User is typing...")
- [ ] Online/offline status indicators
- [ ] Message read receipts
- [ ] Message delivery confirmation
- [ ] Notification sound on new message
- [ ] Unread message count badges
- [ ] Image upload via WebSocket (currently via POST)
- [ ] Message search functionality
- [ ] Message pagination for long conversations

### Performance Optimizations
- [ ] Message caching
- [ ] Connection pooling
- [ ] Load balancing for multiple Daphne workers
- [ ] Message compression

## API Reference

### WebSocket Message Format

**Client → Server (Send Message)**
```json
{
  "message": "Hello, I found your item!",
  "sender_id": 1,
  "recipient_id": 2,
  "item_id": 5,
  "image": null
}
```

**Server → Client (Receive Message)**
```json
{
  "message": "Hello, I found your item!",
  "sender_id": 1,
  "sender_username": "john_doe",
  "timestamp": "Jan. 15, 2025, 03:45 PM",
  "message_id": 42
}
```

## Files Modified

### New Files
- `FindIt/routing.py` - WebSocket URL routing
- `FindIt/consumers.py` - ChatConsumer for real-time messaging
- `REALTIME_MESSAGING.md` - This documentation

### Modified Files
- `lost_and_found/settings.py` - Added Channels configuration
- `lost_and_found/asgi.py` - Configured ASGI with WebSocket support
- `FindIt/templates/FindIt/inbox.html` - Added WebSocket JavaScript client
- `FindIt/views.py` - Updated inbox view comment
- `.github/copilot-instructions.md` - Documented completion

## Dependencies Added
```txt
channels==4.3.1
channels-redis==4.3.0
daphne==4.2.1
```

Add these to `requirements.txt` for deployment.

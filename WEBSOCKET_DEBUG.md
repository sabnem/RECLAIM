# WebSocket Debugging Guide

## Quick Debugging Steps

### Step 1: Open Browser Console
1. Open the inbox page with an active conversation
2. Press **F12** (or right-click → Inspect)
3. Go to the **Console** tab
4. Look for these messages:

**Expected Console Output:**
```
WebSocket Debug Info: {conversationId: "5-2", currentUserId: 1, recipientId: 2, itemId: 5}
Connecting to WebSocket: ws://127.0.0.1:8000/ws/chat/5-2/
✅ WebSocket connection established
```

**If you see errors like:**
```
❌ WebSocket closed unexpectedly
❌ WebSocket error: ...
```
Then continue to Step 2.

### Step 2: Check Network Tab
1. Still in DevTools, click the **Network** tab
2. Click **WS** (WebSocket filter)
3. Refresh the page
4. You should see a connection to `ws/chat/...`
5. Click on it to see:
   - **Status**: Should be "101 Switching Protocols"
   - **Messages**: You can see messages being sent/received

### Step 3: Test Message Sending
1. In the Console tab, type a test message in the chat
2. Look for:
```
📤 Sending message via WebSocket: Hello
Message data: {message: "Hello", sender_id: 1, recipient_id: 2, item_id: 5, image: null}
```

3. Then you should see (if server receives it):
```
📨 Received message: {"message":"Hello","sender_id":1,...}
```

### Step 4: Check Server Terminal
Look at the Django server terminal for errors. You should see:
- WebSocket connection attempts
- Any Python errors from the consumer

### Common Issues & Fixes

#### Issue 1: "WebSocket Error" or "Connection Failed"
**Possible Causes:**
- Server not running with Daphne
- Port not accessible
- ASGI not configured

**Fix:**
```bash
# Restart server
python manage.py runserver
# Look for: "Starting ASGI/Daphne version 4.2.1"
```

#### Issue 2: "conversationId is undefined"
**Possible Cause:** Not in an active conversation

**Fix:**
- Make sure you clicked on a conversation in the sidebar
- URL should have `?item_id=X&recipient_id=Y`

#### Issue 3: Messages send but don't appear for other user
**Possible Causes:**
- Both users not in same conversation room
- Channel layer not working
- JavaScript not appending messages

**Fix:**
1. Check both users have same conversation_id
2. Check Console for "📨 Received message" logs
3. Verify `appendMessage()` function is being called

#### Issue 4: "No module named 'daphne'"
**Fix:**
```bash
pip install channels channels-redis daphne
```

#### Issue 5: Port 8000 already in use
**Fix:**
```powershell
# Windows PowerShell
Get-Process -Name python | Stop-Process -Force
python manage.py runserver
```

```bash
# Linux/Mac
killall python
python manage.py runserver
```

### Manual Testing Script

Open Browser Console and paste this to test WebSocket manually:

```javascript
// Test WebSocket connection manually
const testWS = new WebSocket('ws://127.0.0.1:8000/ws/chat/5-2/');

testWS.onopen = () => console.log('✅ Manual test: Connected');
testWS.onmessage = (e) => console.log('📨 Manual test received:', e.data);
testWS.onerror = (e) => console.error('❌ Manual test error:', e);
testWS.onclose = (e) => console.log('Manual test closed:', e);

// Send test message (replace IDs with your actual IDs)
testWS.send(JSON.stringify({
    message: 'Test message',
    sender_id: 1,
    recipient_id: 2,
    item_id: 5
}));
```

## Checklist Before Testing

- [ ] Server is running: `python manage.py runserver`
- [ ] See "Starting ASGI/Daphne" in terminal
- [ ] No port conflicts (only one server running)
- [ ] Browser console open (F12)
- [ ] Two browser windows ready (regular + incognito)
- [ ] Both users logged in
- [ ] Same conversation open in both windows

## What Should Happen

### User A sends message:
1. Console shows: `📤 Sending message via WebSocket: Hello`
2. Message appears immediately in User A's chat
3. WebSocket sends data to server

### User B receives message:
1. Console shows: `📨 Received message: {...}`
2. Console shows: `Adding message from other user`
3. Message appears in User B's chat **without refresh**

## Still Not Working?

Check these files:

1. **settings.py** - INSTALLED_APPS should have:
   ```python
   'daphne',  # Must be FIRST
   'channels',
   ```

2. **asgi.py** - Should have ProtocolTypeRouter

3. **routing.py** - Should have websocket_urlpatterns

4. **consumers.py** - ChatConsumer should exist

5. **inbox.html** - Should have WebSocket JavaScript

## Enable Verbose Logging

Add this to the Consumer to see what's happening:

```python
# In FindIt/consumers.py - at the top of receive method
async def receive(self, text_data):
    print(f"🔵 WebSocket received: {text_data}")
    # ... rest of code
```

Then watch the server terminal when sending messages.

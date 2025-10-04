# WhatsApp Integration Troubleshooting Guide

## Quick Fix Checklist

### ✅ Issue 1: WhatsApp Token Expired (401 Unauthorized)

**Error Message:**

```
401 Unauthorized
"Error validating access token: Session has expired"
```

**Solution:**

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Select your WhatsApp Business app
3. Navigate to **WhatsApp > API Setup**
4. Generate a new access token:

   - **Temporary Token**: Expires in 24 hours (good for testing)
   - **Permanent Token**: Requires setting up a System User (recommended for production)

5. Update your `.env` file:

```env
WHATSAPP_TOKEN=EAAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=your_custom_verify_token_here
```

6. Restart the Docker container:

```bash
docker-compose restart whatsapp
```

#### Setting Up Permanent Token (Production)

1. In Meta Developer Console, go to **Business Settings > System Users**
2. Create a new System User (e.g., "WhatsApp Bot")
3. Assign the WhatsApp app to this System User
4. Generate a permanent token with `whatsapp_business_messaging` permission
5. Save this token securely - it won't expire!

---

### ✅ Issue 2: Azure OpenAI Connection Dropping

**Error Message:**

```
httpcore.RemoteProtocolError: Server disconnected without sending a response.
```

**What Was Fixed:**

- Added 60-second timeout to prevent hanging connections
- Increased retry attempts from 2 to 3
- Applied to all Azure OpenAI model instances

**Verify Your Azure Configuration:**

Check your `.env` file has correct values:

```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_API_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Model deployment names in Azure
TEXT_MODEL_NAME=gpt-5-chat
SMALL_TEXT_MODEL_NAME=gpt-5-mini
```

**Common Issues:**

- Wrong endpoint URL (should end with `.openai.azure.com/`)
- Incorrect deployment names (must match your Azure OpenAI deployments)
- Rate limiting (check your Azure OpenAI quota)
- Network connectivity from Docker container

---

## Testing After Fixes

### 1. Restart Docker Containers

```bash
# Stop all containers
docker-compose down

# Rebuild and start
docker-compose up --build whatsapp
```

### 2. Check Startup Logs

You should see:

```
WhatsApp module initialized
WHATSAPP_TOKEN configured: True
WHATSAPP_PHONE_NUMBER_ID configured: True
SHORT_TERM_MEMORY_DB_PATH: /app/data/memory.db
```

If any show `False`, those environment variables are missing!

### 3. Monitor Real-Time Logs

```bash
# Watch logs in real-time
docker-compose logs -f whatsapp

# Or if running in foreground, just watch the console
```

### 4. Send Test Message

Send a simple text message to your WhatsApp number. You should see:

```
DEBUG - Full payload: {...}
INFO - Incoming message: type=text from=+1234567890
INFO - Opening database connection to: /app/data/memory.db
DEBUG - Graph invoke: thread_id=+1234567890
INFO - Graph output: workflow=conversation, response_preview='...'
INFO - Message processed
```

---

## Common Errors and Solutions

### Error: "Missing 'entry' in webhook payload"

**Cause:** WhatsApp is sending a different payload structure
**Solution:** Check the logs for "Full payload" and verify the webhook configuration in Meta Developer Console

### Error: "Failed to upload media"

**Cause:** Issue with WhatsApp media upload endpoint
**Solution:** Check your WHATSAPP_TOKEN is valid and has correct permissions

### Error: Database locked

**Cause:** SQLite database file permissions or concurrent access
**Solution:**

```bash
# Stop containers
docker-compose down
# Remove lock file
rm short_term_memory/memory.db-wal
# Restart
docker-compose up whatsapp
```

### Error: "Remote disconnected" (Azure OpenAI)

**Cause:** Network timeout or Azure rate limiting
**Solution:**

- Check Azure OpenAI service health
- Verify your deployment has sufficient quota
- The timeout fixes should help with transient issues

---

## Monitoring Tips

### View Last 100 Lines of Logs

```bash
docker-compose logs --tail=100 whatsapp
```

### Search Logs for Errors

```bash
docker-compose logs whatsapp | grep ERROR
```

### Check Container Status

```bash
docker-compose ps
```

### Access Container Shell (for debugging)

```bash
docker-compose exec whatsapp /bin/bash
```

---

## Environment Variables Reference

Required for WhatsApp:

```env
WHATSAPP_TOKEN=               # Meta access token
WHATSAPP_PHONE_NUMBER_ID=     # WhatsApp Business phone number ID
WHATSAPP_VERIFY_TOKEN=        # Custom token for webhook verification

AZURE_OPENAI_API_KEY=
AZURE_OPENAI_API_ENDPOINT=
AZURE_OPENAI_API_VERSION=

GROQ_API_KEY=                 # For speech-to-text
ELEVENLABS_API_KEY=           # For text-to-speech
ELEVENLABS_VOICE_ID=
TOGETHER_API_KEY=             # For image generation

QDRANT_URL=http://qdrant:6333
QDRANT_PORT=6333
QDRANT_API_KEY=None
```

---

## Next Steps

1. ✅ Fix WhatsApp token (Priority 1)
2. ✅ Verify Azure OpenAI configuration
3. ✅ Restart Docker containers
4. ✅ Test with a simple message
5. ✅ Monitor logs for any new errors

Good luck! 🚀

# Google Calendar Integration Setup Guide

This guide will help you set up Google Calendar integration for your AI companion in just a few minutes.

## Prerequisites

✅ You have `credentials.json` in your project root  
⬜ Google Calendar API enabled  
⬜ OAuth consent screen configured  
⬜ Dependencies installed

## Quick Setup (5 minutes)

### Step 1: Install Dependencies

```bash
# Update dependencies
uv sync

# Or using pip
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Step 2: Run Setup Script

```bash
python scripts/setup_google_calendar.py
```

This script will:

- ✅ Verify your `credentials.json` exists
- ✅ Check all required packages are installed
- ✅ Open your browser for OAuth authorization (first time only)
- ✅ Test calendar access
- ✅ Verify tools are working

**Expected Output:**

```
==============================================================
Google Calendar Integration Setup
==============================================================

📋 Step 1: Checking credentials...
✅ Found credentials.json at /path/to/project/credentials.json

📦 Step 2: Checking dependencies...
✅ google-auth installed
✅ google-auth-oauthlib installed
✅ google-auth-httplib2 installed
✅ google-api-python-client installed

🔐 Step 3: Testing authentication...

📅 Initializing Google Calendar service...
⚠️  This will open your browser for OAuth authorization
   (only needed on first run)

✅ Authentication successful!

📋 Your calendars:
  - Your Calendar
  - Work Calendar

🛠️  Step 4: Testing calendar tools...

🔍 Testing availability check...

Result: ✅ The time slot from 2025-10-04T14:00:00 to 2025-10-04T15:00:00 is available.

✅ Calendar tools are working!

==============================================================
✅ Setup Complete!
==============================================================
```

### Step 3: Test with Your AI Companion

Start your chatbot:

```bash
chainlit run src/ai_companion/interfaces/chainlit/app.py
```

Try these commands:

- "Am I available tomorrow at 2pm?"
- "Check my calendar for next Monday morning"
- "Book a meeting for Friday at 3pm"

## What Happens During Setup?

### First Time Authentication

When you run the setup script (or use calendar tools for the first time):

1. **Browser Opens**: You'll be redirected to Google's OAuth page
2. **Choose Account**: Select the Google account with the calendar you want to access
3. **Grant Permissions**: Click "Allow" to grant calendar access
4. **Token Saved**: A `token.json` file is created in your project root
5. **Done!**: All future requests use this token automatically

### Token Storage

- **`credentials.json`**: Your OAuth client credentials (commit to git)
- **`token.json`**: User-specific access token (in .gitignore, DO NOT commit)

The `token.json` file contains:

- Access token (expires after ~1 hour)
- Refresh token (used to get new access tokens automatically)
- Token expiry timestamp

## Troubleshooting

### Error: credentials.json not found

**Solution:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to "APIs & Services" > "Credentials"
4. Download OAuth 2.0 Client credentials as JSON
5. Rename to `credentials.json` and place in project root

### Error: Google Calendar API not enabled

**Solution:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to "APIs & Services" > "Library"
4. Search for "Google Calendar API"
5. Click "Enable"

### Error: Access denied or insufficient permissions

**Solution:**

1. Check your OAuth consent screen configuration
2. Ensure you're using the correct Google account
3. Delete `token.json` and re-authenticate:
   ```bash
   rm token.json
   python scripts/setup_google_calendar.py
   ```

### Error: Token expired or invalid

The system automatically refreshes expired tokens. If you see this error:

**Solution:**

```bash
# Clear and re-authenticate
rm token.json
python scripts/setup_google_calendar.py
```

### Error: Import errors for google packages

**Solution:**

```bash
# Reinstall dependencies
uv sync
# Or
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## OAuth Consent Screen Setup

If you haven't set up the OAuth consent screen yet:

### 1. Go to OAuth Consent Screen

- Navigate to: [OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)
- Choose "External" (for testing with personal accounts)
- Click "Create"

### 2. Fill App Information

- **App name**: Your AI Companion
- **User support email**: Your email
- **Developer contact**: Your email
- Click "Save and Continue"

### 3. Add Scopes

- Click "Add or Remove Scopes"
- Search for: `https://www.googleapis.com/auth/calendar`
- Select it and click "Update"
- Click "Save and Continue"

### 4. Add Test Users (if External)

- Click "Add Users"
- Add your email address
- Click "Save and Continue"

### 5. Finish

- Review and click "Back to Dashboard"

## Security Best Practices

### ✅ Do's

- ✅ Keep `credentials.json` secure (but can commit to private repos)
- ✅ Add `token.json` to `.gitignore` (already done)
- ✅ Regularly review OAuth consent screen settings
- ✅ Use service accounts for production deployments
- ✅ Limit scopes to only what you need

### ❌ Don'ts

- ❌ Never commit `token.json` to git
- ❌ Don't share `credentials.json` publicly
- ❌ Don't use personal calendars for production
- ❌ Don't grant more permissions than needed

## Production Deployment

For production environments:

### Option 1: Service Account (Recommended)

1. Create a service account in Google Cloud Console
2. Share your calendar with the service account email
3. Use service account credentials instead of OAuth

```python
from google.oauth2 import service_account

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'service-account.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build('calendar', 'v3', credentials=credentials)
```

### Option 2: Store Token Securely

- Use environment variables
- Store in secret management service (AWS Secrets Manager, Google Secret Manager)
- Encrypt token at rest

## Advanced Configuration

### Use Different Calendar

By default, tools use `'primary'` calendar. To use a different calendar:

```python
# In google_calendar_tools.py, replace:
calendarId='primary'

# With:
calendarId='your-calendar-id@group.calendar.google.com'
```

Get calendar ID:

1. Open Google Calendar web
2. Go to Calendar Settings
3. Find "Calendar ID" under "Integrate calendar"

### Custom Timezone

```python
# In google_calendar_tools.py
event = {
    'summary': event_title,
    'start': {
        'dateTime': start_time_formatted,
        'timeZone': 'America/New_York',  # Change this
    },
    # ...
}
```

### Add Reminders

```python
event = {
    # ... other fields
    'reminders': {
        'useDefault': False,
        'overrides': [
            {'method': 'email', 'minutes': 24 * 60},  # 1 day before
            {'method': 'popup', 'minutes': 30},        # 30 min before
        ],
    },
}
```

## Testing

### Unit Tests

```bash
# Test individual tools
python -c "
from ai_companion.modules.calendar.google_calendar_tools import check_calendar_availability
from datetime import datetime, timedelta

tomorrow = datetime.now() + timedelta(days=1)
start = tomorrow.replace(hour=14, minute=0)
end = start + timedelta(hours=1)

result = check_calendar_availability.invoke({
    'start_time': start.isoformat(),
    'end_time': end.isoformat()
})
print(result)
"
```

### Integration Tests

```bash
# Full tool calling test
python examples/test_tool_calling.py
```

### Manual Testing

1. Start your app: `chainlit run src/ai_companion/interfaces/chainlit/app.py`
2. Try these queries:
   - "Am I available tomorrow at 2pm?"
   - "Check my schedule for next week"
   - "Book a 30-minute meeting on Friday at 3pm"
   - "Do I have any meetings today?"

## Monitoring

### Check Authentication Status

```python
from ai_companion.modules.calendar.auth import get_calendar_service

try:
    service = get_calendar_service()
    print("✅ Authenticated successfully")
except Exception as e:
    print(f"❌ Authentication failed: {e}")
```

### Clear Token (for testing)

```python
from ai_companion.modules.calendar.auth import clear_token

clear_token()
# Next API call will re-authenticate
```

## FAQ

**Q: Do I need to re-authenticate every time?**  
A: No! The `token.json` file stores your credentials. You only authenticate once.

**Q: What if I delete token.json?**  
A: Just run the setup script again. It will re-authenticate.

**Q: Can multiple users use the same credentials.json?**  
A: Yes, but each user needs their own `token.json`. For multi-user apps, implement user-specific token storage.

**Q: How much does this cost?**  
A: Google Calendar API is free for reasonable usage (up to 1 million requests/day).

**Q: Can I use this with G Suite/Workspace accounts?**  
A: Yes! Just authenticate with your workspace account.

**Q: How do I revoke access?**  
A: Go to [Google Account Permissions](https://myaccount.google.com/permissions) and remove your app.

## Next Steps

✅ Setup complete? Great!  
👉 Read: [Tool Calling Guide](TOOL_CALLING_GUIDE.md)  
👉 See: [Architecture Diagram](TOOL_CALLING_ARCHITECTURE.md)  
👉 Test: `python examples/test_tool_calling.py`

---

**Need help?** Open an issue or check the troubleshooting section above.

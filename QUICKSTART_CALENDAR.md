# 🚀 Quick Start: Google Calendar Integration

Your Google Calendar integration is almost ready! Follow these 3 simple steps:

## Step 1: Install Dependencies (30 seconds)

```bash
uv sync
```

## Step 2: Run Setup Script (2 minutes)

```bash
python scripts/setup_google_calendar.py
```

**What happens:**

- ✅ Verifies credentials.json ← You already have this!
- ✅ Checks dependencies
- 🌐 Opens browser for Google OAuth (first time only)
- ✅ Tests calendar access
- ✅ Creates token.json automatically

**During OAuth:**

1. Browser opens → Google login page
2. Choose your Google account
3. Click "Allow" to grant calendar access
4. Browser closes → You're done!

## Step 3: Test It! (1 minute)

Start your AI companion:

```bash
chainlit run src/ai_companion/interfaces/chainlit/app.py
```

Try these commands:

- **"Am I available tomorrow at 2pm?"**
- **"Book a meeting for Friday at 3pm"**
- **"Check my calendar for next week"**

---

## ✅ That's It!

Your bot now has calendar superpowers! 🎉

### What Was Changed?

✅ Real Google Calendar API integration (no more mock responses)  
✅ Automatic OAuth authentication  
✅ Token management (auto-refresh)  
✅ Error handling for API failures  
✅ Timezone support

### Files Modified:

- ✅ `pyproject.toml` - Added Google API dependencies
- ✅ `src/ai_companion/modules/calendar/auth.py` - OAuth handler (NEW)
- ✅ `src/ai_companion/modules/calendar/google_calendar_tools.py` - Real API calls
- ✅ `.gitignore` - Added token.json

### Security:

- ✅ `token.json` is in .gitignore (won't be committed)
- ✅ Auto token refresh (no manual re-auth needed)
- ✅ Secure OAuth 2.0 flow

---

## Troubleshooting

**"credentials.json not found"**
→ Make sure it's in the project root directory

**"Import errors"**
→ Run: `uv sync`

**"Authentication failed"**
→ Delete token.json and run setup again

**Need more help?**
→ See: `docs/GOOGLE_CALENDAR_SETUP.md`

---

## What's Next?

- 📖 Read the full guide: `docs/GOOGLE_CALENDAR_SETUP.md`
- 🏗️ Understand the architecture: `docs/TOOL_CALLING_ARCHITECTURE.md`
- 🧪 Run integration tests: `python examples/test_tool_calling.py`

**Enjoy your AI companion with calendar powers! 🤖📅**

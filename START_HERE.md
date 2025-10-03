# 🎯 START HERE - Google Calendar Integration

## ✅ What You Already Have

- ✅ `credentials.json` in project root
- ✅ All code updated and ready to go

## 🚀 What You Need to Do (3 Steps)

### Step 1: Install Dependencies (30 seconds)

```bash
uv sync
```

### Step 2: Authenticate with Google (2 minutes)

```bash
python scripts/setup_google_calendar.py
```

**This will:**

- ✅ Open your browser
- ✅ Ask you to log in to Google
- ✅ Request calendar permissions
- ✅ Save authentication token
- ✅ Test everything works

### Step 3: Test It! (1 minute)

```bash
# Start your app
chainlit run src/ai_companion/interfaces/chainlit/app.py

# Then ask your bot:
"Am I available tomorrow at 2pm?"
```

---

## 📖 Documentation

| File                                    | What It Does                     |
| --------------------------------------- | -------------------------------- |
| **`QUICKSTART_CALENDAR.md`**            | Quick 3-step guide (start here)  |
| **`CALENDAR_INTEGRATION_SUMMARY.md`**   | Complete overview of changes     |
| **`docs/GOOGLE_CALENDAR_SETUP.md`**     | Detailed setup & troubleshooting |
| **`docs/TOOL_CALLING_ARCHITECTURE.md`** | How it works (diagrams)          |

---

## 🎉 That's It!

After Step 2, you'll have a `token.json` file and your bot will be able to:

- ✅ Check your real Google Calendar availability
- ✅ Book events in your calendar
- ✅ List conflicting events
- ✅ Send calendar invites

**The setup script will guide you through everything!**

---

## ⚡ Quick Commands

```bash
# First time setup
uv sync
python scripts/setup_google_calendar.py

# Start your app
chainlit run src/ai_companion/interfaces/chainlit/app.py

# Run tests
python examples/test_tool_calling.py

# Re-authenticate (if needed)
rm token.json
python scripts/setup_google_calendar.py
```

---

**Ready? Run the commands above! 🚀**

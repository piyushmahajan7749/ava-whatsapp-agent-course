# 📊 Google Sheets Setup - Step by Step

**Follow these steps to complete your setup:**

---

## Step 1: Create Your Google Sheet (2 minutes)

### **Option A: Create Manually**

1. Go to [sheets.google.com](https://sheets.google.com)
2. Click **"+ Blank"** to create a new spreadsheet
3. Name it: **"Upaai Bookings"**
4. Create two sheets (tabs at the bottom):
   - Click **"+"** at the bottom-left
   - Rename "Sheet1" to **"Consultations"**
   - Add another sheet and name it **"Products"**

### **Option B: Use This Template Link**

[Click here to create from template](https://docs.google.com/spreadsheets/create)

Then:

- Name it: "Upaai Bookings"
- Create sheets: "Consultations" and "Products"

---

## Step 2: Get Your Spreadsheet ID (30 seconds)

1. Open your newly created sheet
2. Look at the URL in your browser:
   ```
   https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                         THIS IS YOUR SPREADSHEET ID
   ```
3. **Copy the ID** (the long string between `/d/` and `/edit`)

---

## Step 3: Add to .env File (1 minute)

1. Open your `.env` file in the project root
2. Add this line (replace with your actual ID):
   ```bash
   GOOGLE_SHEETS_BOOKING_ID="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
   ```
3. Save the file

---

## Step 4: Run Setup Script (1 minute)

Run this command:

```bash
cd /Users/piyush/Projects/cx-agent
export PYTHONPATH=/Users/piyush/Projects/cx-agent/src
python scripts/setup_google_sheets.py
```

**What this does:**

- Adds headers to your sheets
- Formats headers (bold, gray background)
- Freezes the first row
- Auto-resizes columns

---

## Step 5: Verify (30 seconds)

1. Open your Google Sheet
2. Check that both sheets have headers
3. "Consultations" sheet should have 17 columns
4. "Products" sheet should have 18 columns

---

## ✅ Done!

Now every booking will automatically be logged to your Google Sheet!

---

## 🐛 Troubleshooting

### **"No module named 'ai_companion'"**

Run with PYTHONPATH:

```bash
export PYTHONPATH=/Users/piyush/Projects/cx-agent/src
```

### **"GOOGLE_SHEETS_BOOKING_ID not set"**

Make sure you:

1. Added the line to `.env`
2. Used the correct Spreadsheet ID
3. Saved the `.env` file

### **"credentials.json not found"**

You need Google Cloud credentials. See `docs/GOOGLE_CALENDAR_SETUP.md` for instructions.

---

## 📞 Need Help?

Refer to:

- **Quick Start**: `GOOGLE_SHEETS_QUICKSTART.md`
- **Full Guide**: `docs/GOOGLE_SHEETS_INTEGRATION.md`

---

**Ready?** Create your sheet and let me know the Spreadsheet ID! 🚀

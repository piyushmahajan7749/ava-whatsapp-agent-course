# 📊 Google Sheets Integration - Quick Start

**Feature**: Automatic booking logs to Google Sheets

---

## 🎯 What You Need

1. ✅ Google Sheet with two tabs: `Consultations` and `Products`
2. ✅ Spreadsheet ID from the URL
3. ✅ Updated `.env` configuration
4. ✅ Re-authentication (if you were already using Calendar)

---

## ⚡ 5-Minute Setup

### **Step 1: Create Your Sheet** (2 min)

1. Go to [sheets.google.com](https://sheets.google.com)
2. Create new spreadsheet: **"Upaai Bookings"**
3. Create two sheets (tabs):
   - `Consultations`
   - `Products`

### **Step 2: Get Spreadsheet ID** (30 sec)

Copy from URL:

```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                         This is your Spreadsheet ID
```

### **Step 3: Configure** (1 min)

Add to `.env`:

```bash
GOOGLE_SHEETS_BOOKING_ID="your_spreadsheet_id_here"
```

### **Step 4: Re-authenticate** (30 sec)

```bash
# Delete old token
rm token.json

# Next API call will prompt for re-auth
# Accept Google Sheets permission
```

### **Step 5: Initialize Headers** (1 min)

```bash
python scripts/setup_google_sheets.py
```

---

## ✅ You're Done!

Now every booking will automatically appear in your Google Sheet!

---

## 🧪 Quick Test

1. **Make a booking** through your app
2. **Open Google Sheet**
3. **Go to Consultations tab**
4. **See the new row** with all booking details!

---

## 📊 What Gets Logged

**Consultations:**

- Customer name, DOB, contact
- Appointment date/time
- Payment amount (including split payments!)
- Calendar event link
- Booking ID, thread ID, status

**Products** (when you use the API):

- Product type, name
- Customer details, gotra
- Shipping address
- Payment info
- Order status, tracking

---

## 🔧 API Usage (Optional)

Want to log manually?

```python
from ai_companion.modules.sheets import log_consultation_booking

log_consultation_booking(
    customer_name="Rahul Sharma",
    date_of_birth="1990-05-15",
    consultation_datetime="2025-10-08T10:00:00+05:30",
    payment_amount=2100,
    payment_details="2000 + 100",  # For split payments
    thread_id="user_123"
)
```

---

## 💡 Pro Tips

### **Share with Team**

Click **Share** button → Add team emails → Set as **Viewer**

### **Protect Headers**

1. Select first row
2. Right-click → **Protect range**
3. Prevents accidental deletion

### **Quick Analytics**

Add these formulas:

- **Total Revenue**: `=SUM(I:I)`
- **Booking Count**: `=COUNTA(B:B) - 1`
- **Split Payment %**: `=COUNTIF(K:K,"TRUE")/(COUNTA(K:K)-1)`

---

## 🐛 Common Issues

### **"GOOGLE_SHEETS_BOOKING_ID not set"**

→ Add to `.env` file

### **"Insufficient permissions"**

→ Delete `token.json` and re-auth

### **Booking works but no Sheets entry**

→ Check logs for error message  
→ Verify Spreadsheet ID is correct  
→ Ensure sheet tabs are named exactly: `Consultations` and `Products`

---

## 📚 Full Documentation

See [`docs/GOOGLE_SHEETS_INTEGRATION.md`](docs/GOOGLE_SHEETS_INTEGRATION.md) for:

- Complete schema details
- Advanced usage
- Business analytics
- Troubleshooting guide

---

## ✅ That's It!

Your bookings are now automatically logged to Google Sheets! 🎉

**Next**: Share the sheet with your team and start analyzing booking data!

# 📊 Google Sheets Integration - Booking Logs

**Date**: October 6, 2025  
**Status**: ✅ **IMPLEMENTED**  
**Feature**: Automatic booking logs to Google Sheets

---

## 🎯 Overview

Automatically logs all confirmed consultation bookings and product orders to Google Sheets, creating a centralized business record that's accessible to your entire team.

### **What Gets Logged**

✅ **Consultation Bookings**

- Customer details (name, DOB, contact)
- Appointment date/time
- Payment information (including split payments)
- Calendar event links
- Booking status

✅ **Product Orders** (Ready to implement)

- Product type (Kalawa, Yantra, Puja)
- Customer information
- Shipping address
- Payment details
- Order status and tracking

---

## 🏗️ Architecture

### **Module Structure**

```
src/ai_companion/modules/
├── calendar/
│   ├── auth.py                    # Updated with Sheets scope
│   └── google_calendar_tools.py   # Integrated Sheets logging
└── sheets/
    ├── __init__.py
    └── sheets_manager.py           # Core Sheets operations
```

### **Data Flow**

```
User completes payment
    ↓
payment_verification_node verifies payment
    ↓
conversation_node collects booking details
    ↓
book_calendar_event tool creates calendar event
    ↓ (SUCCESS)
log_consultation_booking writes to Sheets
    ↓
Business team can view booking in Google Sheets
```

---

## 📋 Sheet Schema

### **Consultations Sheet**

| Column                | Description             | Example                           |
| --------------------- | ----------------------- | --------------------------------- |
| **Timestamp**         | When booking was logged | `2025-10-06 08:30:15`             |
| **Booking ID**        | Unique identifier       | `CONS_20251006_083015`            |
| **Customer Name**     | Full name               | `Rahul Sharma`                    |
| **Date of Birth**     | For consultation        | `1990-05-15`                      |
| **Phone/Email**       | Contact info            | `+91 9876543210`                  |
| **Consultation Date** | Scheduled date          | `2025-10-08`                      |
| **Consultation Time** | Scheduled time (IST)    | `10:00 AM`                        |
| **Duration**          | Call duration           | `30 minutes`                      |
| **Payment Amount**    | Total paid (₹)          | `2100`                            |
| **Payment Mode**      | Payment method          | `UPI`                             |
| **Split Payment**     | Multiple payments?      | `TRUE` / `FALSE`                  |
| **Payment Details**   | Split breakdown         | `2000 + 100`                      |
| **Calendar Event ID** | Google Calendar ID      | `abc123xyz`                       |
| **Calendar Link**     | Link to event           | `https://calendar.google.com/...` |
| **Thread ID**         | User session ID         | `user_123`                        |
| **Status**            | Booking status          | `Confirmed`                       |
| **Notes**             | Additional info         | `Prefers Hindi`                   |

### **Products Sheet**

| Column               | Description           | Example                        |
| -------------------- | --------------------- | ------------------------------ |
| **Timestamp**        | When order was placed | `2025-10-06 09:15:30`          |
| **Order ID**         | Unique identifier     | `PROD_20251006_091530`         |
| **Product Type**     | Category              | `Apamarg Jad Kalawa`           |
| **Product Name**     | Specific product      | `Kalawa - Blessed on Purnima`  |
| **Customer Name**    | Full name             | `Priya Gupta`                  |
| **Gotra**            | Family lineage        | `Kashyap`                      |
| **Phone/Email**      | Contact               | `priya@example.com`            |
| **Shipping Address** | Full address          | `123, MG Road, Delhi - 110001` |
| **Payment Amount**   | Amount paid (₹)       | `2100`                         |
| **Payment Mode**     | Payment method        | `UPI`                          |
| **Split Payment**    | Multiple payments?    | `FALSE`                        |
| **Payment Details**  | Split breakdown       | `-`                            |
| **Puja Date**        | If applicable         | `2025-10-15` (Purnima)         |
| **Thread ID**        | Session ID            | `user_456`                     |
| **Order Status**     | Fulfillment status    | `Pending Blessing`             |
| **Dispatch Date**    | When shipped          | `2025-10-17`                   |
| **Tracking ID**      | Courier tracking      | `DTDC123456`                   |
| **Notes**            | Special instructions  | `Urgent delivery`              |

---

## 🚀 Setup Guide

### **Step 1: Create Google Sheet**

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Name it **"Upaai Bookings"**
4. Create two sheets (tabs):
   - `Consultations`
   - `Products`

### **Step 2: Get Spreadsheet ID**

1. Open your spreadsheet
2. Copy the ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
   ```
3. Example ID: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`

### **Step 3: Configure Environment**

Add to your `.env` file:

```bash
# Google Sheets Configuration
GOOGLE_SHEETS_BOOKING_ID="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
```

Replace with your actual Spreadsheet ID.

### **Step 4: Re-authenticate (If Needed)**

If you've already authenticated for Google Calendar, you'll need to re-authenticate to include Sheets permission:

```bash
# Delete existing token
rm token.json

# Next API call will trigger re-authentication
# You'll be prompted to authorize Google Sheets access
```

**Why?** The authentication scope was expanded to include `https://www.googleapis.com/auth/spreadsheets`.

### **Step 5: Initialize Sheet Headers**

Run the setup script to add headers and formatting:

```bash
cd /Users/piyush/Projects/cx-agent
python scripts/setup_google_sheets.py
```

**What this does:**

- Adds column headers to both sheets
- Applies bold formatting to headers
- Sets gray background color
- Freezes the first row
- Auto-resizes columns

---

## 🧪 Testing

### **Test 1: Complete Booking Flow**

```bash
# Start your application
python -m ai_companion.interfaces.chainlit.app

# Test booking:
User: "I want to book a consultation"
Agent: "Please send payment screenshot"

User: [Sends ₹2,100 payment screenshot]
Agent: "Payment verified! Please share your name and DOB"

User: "My name is Rahul Sharma, DOB 1990-05-15"
Agent: "Let me check available slots..."

# Agent books in calendar AND logs to Sheets automatically
```

### **Test 2: Verify Sheets Data**

1. Open your Google Sheet
2. Go to "Consultations" tab
3. You should see a new row with:
   - Timestamp
   - Unique Booking ID
   - Customer details
   - Payment info
   - Calendar event link

### **Test 3: Split Payment Tracking**

```bash
User: [Sends ₹2,000 screenshot]
Agent: "₹2,000 received! Need ₹100 more"

User: [Sends ₹100 screenshot]
Agent: "Total ₹2,100 verified!"

# After booking, Sheets will show:
# - Split Payment: TRUE
# - Payment Details: "2000 + 100"
```

---

## 🔧 API Usage

### **Log Consultation Booking**

```python
from ai_companion.modules.sheets import log_consultation_booking

result = log_consultation_booking(
    customer_name="Rahul Sharma",
    date_of_birth="1990-05-15",
    consultation_datetime="2025-10-08T10:00:00+05:30",
    payment_amount=2100,
    payment_details="2000 + 100",  # For split payments
    calendar_event_id="abc123xyz",
    calendar_link="https://calendar.google.com/event?eid=...",
    thread_id="user_123",
    contact_info="+91 9876543210",
    notes="Prefers Hindi communication"
)

if result['success']:
    print(f"✅ Logged as {result['booking_id']}")
else:
    print(f"❌ Error: {result['error']}")
```

### **Log Product Order**

```python
from ai_companion.modules.sheets import log_product_order

result = log_product_order(
    product_type="Apamarg Jad Kalawa",
    product_name="Kalawa - Blessed on Purnima",
    customer_name="Priya Gupta",
    payment_amount=2100,
    shipping_address="123, MG Road, Delhi - 110001",
    gotra="Kashyap",
    contact_info="priya@example.com",
    thread_id="user_456"
)

if result['success']:
    print(f"✅ Order {result['order_id']} logged")
```

---

## 📊 Business Analytics

### **Ready-to-Use Formulas**

Add these to new columns for instant insights:

**Total Revenue (Consultations):**

```
=SUM(I:I)
```

**Number of Bookings:**

```
=COUNTA(B:B) - 1
```

**Split Payment Rate:**

```
=COUNTIF(K:K, "TRUE") / (COUNTA(K:K) - 1)
```

**Average Booking Value:**

```
=AVERAGE(I:I)
```

### **Pivot Table Ideas**

1. **Revenue by Date**

   - Rows: Consultation Date
   - Values: SUM of Payment Amount

2. **Booking Status Breakdown**

   - Rows: Status
   - Values: COUNTA of Booking ID

3. **Split Payment Analysis**
   - Rows: Split Payment
   - Values: COUNT, AVG of Payment Amount

---

## 🔐 Security & Permissions

### **Share with Team**

1. Open your Google Sheet
2. Click **Share** button
3. Add team members:
   - **Viewer**: Can view data only
   - **Commenter**: Can add comments
   - **Editor**: Can modify data (be careful!)

### **Recommended Permissions**

- **Business Team**: Viewer
- **Customer Support**: Viewer
- **Admin**: Editor
- **System (your app)**: Editor (via service account)

### **Protect Headers**

1. Select first row (headers)
2. Right-click → **Protect range**
3. Set permissions: "Only you"
4. This prevents accidental header deletion

---

## ⚙️ Configuration

### **Change Sheet Names**

Edit `src/ai_companion/modules/sheets/sheets_manager.py`:

```python
CONSULTATIONS_SHEET_NAME = "Consultations"  # Change to your preference
PRODUCTS_SHEET_NAME = "Products"            # Change to your preference
```

### **Add Custom Columns**

1. Update sheet schema in Google Sheets (add column)
2. Modify `log_consultation_booking()` or `log_product_order()` in `sheets_manager.py`
3. Add new field to `row_data` list
4. Update range (e.g., `A:Q` → `A:R` for one new column)

---

## 🐛 Troubleshooting

### **Error: "GOOGLE_SHEETS_BOOKING_ID not set"**

**Solution:**

1. Create Google Sheet
2. Copy Spreadsheet ID from URL
3. Add to `.env`: `GOOGLE_SHEETS_BOOKING_ID='your_id_here'`

### **Error: "credentials.json not found"**

**Solution:**

1. Ensure `credentials.json` is in project root
2. Download from Google Cloud Console if missing

### **Error: "Insufficient permissions"**

**Solution:**

1. Delete `token.json`
2. Run setup script again to re-authenticate
3. Accept all requested permissions

### **Booking succeeds but Sheets write fails**

**This is intentional behavior!**

Sheets logging is supplementary - if it fails, the calendar booking still succeeds. Check logs:

```bash
# Look for these log messages:
⚠️  Failed to log booking to Sheets: [error message]
```

Common causes:

- Spreadsheet ID incorrect
- Sheet doesn't exist
- Network issues

---

## 🔄 Migration from Existing System

If you have existing bookings to import:

1. **Export from current system** (CSV format)
2. **Open your Sheets**
3. **File → Import → Upload**
4. **Match columns** to your schema
5. **Append to existing sheet**

---

## 📈 Future Enhancements

### **Phase 1: Advanced Analytics** (Planned)

- Revenue dashboard
- Booking trends over time
- Customer retention metrics
- Popular time slots

### **Phase 2: Automated Workflows** (Planned)

- Send confirmation emails from Sheets
- Automated reminders 24h before consultation
- WhatsApp notifications for product dispatch

### **Phase 3: Integration** (Planned)

- Export to accounting software
- CRM integration
- Automated invoicing

---

## 📚 Related Documentation

- [Google Calendar Setup](GOOGLE_CALENDAR_SETUP.md)
- [Payment Verification](PAYMENT_VERIFICATION_SUMMARY.md)
- [Split Payment Support](SPLIT_PAYMENT_SUPPORT.md)
- [Intent Routing](INTENT_ROUTING_IMPLEMENTATION.md)

---

## ✅ Summary

| Feature                    | Status                 |
| -------------------------- | ---------------------- |
| **Sheets Authentication**  | ✅ Implemented         |
| **Consultations Logging**  | ✅ Implemented         |
| **Products Logging**       | ✅ Ready (API created) |
| **Split Payment Tracking** | ✅ Implemented         |
| **Setup Script**           | ✅ Implemented         |
| **Error Handling**         | ✅ Implemented         |
| **Documentation**          | ✅ Complete            |

---

**Implementation Date**: October 6, 2025  
**Feature**: Google Sheets Integration  
**Status**: ✅ **PRODUCTION READY**

🎉 **All consultation bookings are now automatically logged to Google Sheets!**

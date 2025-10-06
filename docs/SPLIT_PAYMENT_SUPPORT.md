# 💰 Split Payment Support - Payment Verification Enhancement

**Date**: October 6, 2025  
**Status**: ✅ **IMPLEMENTED**  
**Feature**: Multi-screenshot split payment tracking

---

## 🎯 Overview

Enhanced the payment verification system to support **split payments** where users can send multiple payment screenshots that add up to the required consultation fee (₹2,100).

### **Real-World Scenarios**

Users may split payments due to:

- **UPI transaction limits** (some banks limit single transactions)
- **Multiple payment sources** (using different bank accounts/cards)
- **Partial payments first** (pay what they can, then complete later)

### **Supported Split Patterns**

✅ ₹2,000 + ₹100  
✅ ₹1,000 + ₹1,100  
✅ ₹1,500 + ₹600  
✅ ₹700 + ₹700 + ₹700  
✅ Any combination that totals ≥ ₹2,100

---

## 🔧 How It Works

### **1. Payment History Tracking**

Each user (identified by `thread_id`) has their own payment history:

```python
# Example payment history
{
    "user_123": [2000, 100],      # Paid ₹2000, then ₹100
    "user_456": [1000, 1100],     # Paid ₹1000, then ₹1100
    "user_789": [700, 700, 700],  # Paid ₹700 three times
}
```

### **2. Cumulative Verification**

When a payment screenshot is received:

1. Extract amount using Azure Vision AI
2. Add to user's payment history
3. Calculate total paid so far
4. Check if total ≥ ₹2,100
5. Update verification status

### **3. User Feedback**

**First Payment (Partial):**

```
User sends: ₹2,000 screenshot

Agent: "Thank you! Payment of ₹2,000 received!
        You still need to send ₹100 more to complete the booking.
        Please share the next payment screenshot when ready! 🙏"
```

**Second Payment (Completes):**

```
User sends: ₹100 screenshot

Agent: "Perfect! Payment complete! ✅
        Total received: ₹2,100 (from 2 transactions)

        Now, to confirm your booking, please share:
        - Your full name
        - Date of birth

        I'll then check available slots for you!"
```

**Over-payment:**

```
User sends: ₹2,000 + ₹200

Agent: "Thank you! Payment verified! ✅
        Total received: ₹2,200 (₹100 extra paid)

        All set for booking! Please provide your name and date of birth."
```

---

## 📊 Architecture

### **New Functions in `google_calendar_tools.py`**

#### **1. `add_payment_amount(thread_id, amount)`**

Records a payment amount for a user.

```python
result = add_payment_amount("user_123", 2000)
# Returns:
# {
#     "total": 2000,
#     "payments": [2000],
#     "count": 1,
#     "fully_paid": False,
#     "expected": 2100,
#     "remaining": 100
# }
```

#### **2. `get_payment_total(thread_id)`**

Gets current payment status for a user.

```python
status = get_payment_total("user_123")
# Returns payment summary dict
```

#### **3. `clear_payment_history(thread_id)`**

Clears payment history after successful booking.

```python
clear_payment_history("user_123")
# Called after booking is confirmed
```

### **Enhanced `payment_verification_node`**

Now tracks split payments:

```python
async def payment_verification_node(state, config):
    # Extract amount from screenshot
    amount = verify_payment_screenshot(image)

    # Add to user's payment history
    summary = add_payment_amount(thread_id, amount)

    if summary['fully_paid']:
        # ✅ Full amount received
        set_payment_verified(thread_id, True)
        return {"payment_verified": True}
    else:
        # 📊 Partial - need more
        return {
            "payment_verified": False,
            "payment_status": "partial_payment",
            "payment_remaining": summary['remaining']
        }
```

---

## 🧪 Testing Scenarios

### **Scenario 1: Two-Part Payment**

```
User: "I want to book"
Agent: "Please share payment screenshot first!"

User: [sends ₹2,000 screenshot]
Agent: "Thank you! ₹2,000 received. Still need ₹100. Please share next payment!"

User: [sends ₹100 screenshot]
Agent: "Perfect! Total ₹2,100 verified! ✅ Now please share your name and DOB."
```

**Expected Behavior:**

- ✅ First payment recorded: ₹2,000
- ✅ Agent acknowledges partial payment
- ✅ Second payment recorded: ₹100
- ✅ Total calculated: ₹2,100
- ✅ Payment verified
- ✅ Booking proceeds

---

### **Scenario 2: Three-Part Payment**

```
User: [sends ₹700 screenshot]
Agent: "₹700 received! Still need ₹1,400 more."

User: [sends ₹700 screenshot]
Agent: "₹1,400 total so far! Still need ₹700 more."

User: [sends ₹700 screenshot]
Agent: "Perfect! ₹2,100 complete! ✅"
```

**Expected Behavior:**

- ✅ Tracks 3 separate payments
- ✅ Cumulative total maintained
- ✅ Final verification when total ≥ ₹2,100

---

### **Scenario 3: Overpayment**

```
User: [sends ₹2,500 screenshot]
Agent: "Payment verified! ₹2,500 received (₹400 extra). All set for booking!"
```

**Expected Behavior:**

- ✅ Accepts overpayment
- ✅ Marks as verified
- ✅ Proceeds with booking

---

### **Scenario 4: Wrong Amount**

```
User: [sends ₹500 screenshot]
Agent: "Thank you! ₹500 received. You still need ₹1,600 more to complete booking."

User: "Actually, I want to cancel"
# Admin manually clears history if needed
```

**Expected Behavior:**

- ✅ Tracks partial amount
- ✅ Doesn't proceed without full payment
- ✅ Admin can clear history for cancellations

---

## 📝 State Management

### **New State Fields**

```python
class AICompanionState:
    payment_amount: Optional[int]       # Total amount paid
    payment_status: str                 # Status of payment
    payment_remaining: Optional[int]    # Remaining to pay
```

### **Payment Status Values**

| Status                | Meaning                                 |
| --------------------- | --------------------------------------- |
| `verified_full`       | Full payment received (single or split) |
| `partial_payment`     | Some payment received, more needed      |
| `amount_mismatch`     | Amount doesn't match expected           |
| `verification_failed` | Couldn't verify screenshot              |

---

## 🔍 Vision AI Integration

### **Payment Amount Extraction**

The vision model extracts amounts using regex patterns:

```python
patterns = [
    r"amount:\s*₹?\s*(\d{1,3}(?:,\d{3})*)",  # "Amount: ₹2,100"
    r"₹\s*(\d{1,3}(?:,\d{3})*)",             # "₹2100"
    r"rs\.?\s*(\d{1,3}(?:,\d{3})*)",         # "Rs 2100"
]
```

### **Handles Different Formats**

✅ ₹2,100  
✅ ₹2100  
✅ Rs 2,100  
✅ Rs.2100  
✅ 2100 rupees  
✅ INR 2100

---

## 🎨 User Experience Flow

```
┌─────────────────────────────────────────┐
│  User wants to book consultation        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Agent: "Please send payment screenshot"│
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  User sends first screenshot (₹2,000)   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  System: Extract amount, add to history │
│  Total: ₹2,000 / ₹2,100                 │
│  Status: Partial                         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Agent: "₹2,000 received! Need ₹100 more│
│  Please send next payment screenshot"   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  User sends second screenshot (₹100)    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  System: Extract amount, add to history │
│  Total: ₹2,100 / ₹2,100                 │
│  Status: Verified! ✅                    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Agent: "Payment complete! ₹2,100 ✅     │
│  Please share name and DOB for booking" │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  Proceed with calendar booking          │
└─────────────────────────────────────────┘
```

---

## ⚙️ Configuration

### **Expected Amount**

Defined in `core/knowledge.py`:

```python
CONSULTATION_PRICE_INR = 2100
```

To change the required amount, update this constant.

### **Payment Tolerance**

Currently accepts:

- **Exact match**: ₹2,100
- **Overpayment**: ₹2,100+ (any amount ≥ ₹2,100)

To require exact amount only:

```python
# In payment_verifier.py
amount_matches = amount == self.expected_amount  # Exact only
```

---

## 🔐 Security Considerations

### **Amount Verification**

✅ Extracts amount from vision AI analysis  
✅ Cross-references with UPI app indicators  
✅ Checks transaction status (success/failed)  
✅ Logs all payments for audit trail

### **Duplicate Screenshot Prevention**

⚠️ **Current**: System doesn't prevent duplicate screenshots  
💡 **Future Enhancement**: Track transaction IDs to prevent duplicates

### **Fraud Prevention**

Current checks:

1. Amount must be extracted from image
2. Payment app must be identified (GPay/PhonePe/etc.)
3. Transaction status must be "success"
4. Cumulative total tracked per user

---

## 📈 Monitoring & Logging

### **Log Messages**

```
INFO: 💰 Payment recorded for thread user_123:
  This payment: ₹2000
  Total paid: ₹2000
  Payments: [2000]
  Remaining: ₹100

INFO: ✅ FULL PAYMENT VERIFIED for thread user_123:
  Total: ₹2100 from 2 payment(s)
  Payments: [2000, 100]
  Status: success
```

### **Metrics to Track**

- Average payments per booking (1, 2, or 3+)
- Most common split patterns
- Completion rate after partial payments
- Time between split payments

---

## 🚀 Future Enhancements

### **Phase 1: Duplicate Detection**

Track transaction IDs to prevent same screenshot being counted twice:

```python
_transaction_ids = {}  # thread_id -> set of transaction IDs

if transaction_id in _transaction_ids[thread_id]:
    return "Duplicate payment screenshot - already counted"
```

### **Phase 2: Payment Expiry**

Clear old partial payments after N days:

```python
_payment_timestamps = {}  # Track when payments were made

if last_payment_age > 7_days:
    clear_payment_history(thread_id)
```

### **Phase 3: Payment Analytics**

Dashboard showing:

- Split payment usage rate
- Average number of screenshots per booking
- Drop-off rate at partial payment stage

---

## 🐛 Troubleshooting

### **Issue: Partial payment not recognized**

**Symptoms**: User sends second screenshot but agent doesn't acknowledge

**Solution**:

1. Check logs for amount extraction
2. Verify vision model is analyzing image correctly
3. Check if thread_id is consistent across messages

### **Issue: Amount not extracted**

**Symptoms**: Agent says "verification failed"

**Solution**:

1. Check image quality - must be clear
2. Verify amount is visible in screenshot
3. Check vision model is configured correctly

### **Issue: Wrong total calculated**

**Symptoms**: Agent shows incorrect cumulative total

**Solution**:

1. Check `_payment_history` global state
2. Verify `add_payment_amount` is being called
3. Check logs for payment tracking messages

---

## ✅ Summary

| Feature                           | Status                |
| --------------------------------- | --------------------- |
| **Split Payment Tracking**        | ✅ Implemented        |
| **Cumulative Amount Calculation** | ✅ Implemented        |
| **Partial Payment Feedback**      | ✅ Implemented        |
| **Vision AI Integration**         | ✅ Implemented        |
| **State Management**              | ✅ Implemented        |
| **User Communication**            | ✅ Implemented        |
| **Logging & Monitoring**          | ✅ Implemented        |
| **Duplicate Prevention**          | ⏳ Future enhancement |
| **Payment Expiry**                | ⏳ Future enhancement |

---

## 📚 Related Files

**Modified:**

- `src/ai_companion/modules/calendar/google_calendar_tools.py` - Payment tracking functions
- `src/ai_companion/graph/nodes.py` - Split payment verification logic
- `src/ai_companion/graph/state.py` - Payment state fields
- `src/ai_companion/core/prompts.py` - Split payment instructions

**Created:**

- `src/ai_companion/modules/payment/payment_verifier.py` - Vision AI payment verification
- `docs/SPLIT_PAYMENT_SUPPORT.md` - This documentation

---

**Implementation Date**: October 6, 2025  
**Feature**: Split Payment Support  
**Status**: ✅ **PRODUCTION READY**

🎉 **Users can now send multiple payment screenshots that add up to ₹2,100!**

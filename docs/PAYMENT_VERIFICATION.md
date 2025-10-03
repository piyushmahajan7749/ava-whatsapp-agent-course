# Payment Verification for Appointment Booking

## Overview

A strict payment verification system that ensures users submit payment proof before booking appointments through the calendar system.

## How It Works

### Architecture

```
User Message → Payment Verification Node → Calendar Booking Tool
                      ↓
              Detects Payment Screenshot
                      ↓
            Sets payment_verified = True
                      ↓
         Allows Booking to Proceed
```

### Components

#### 1. **State Management** (`state.py`)

- Added `payment_verified: bool` field to `AICompanionState`
- Tracks whether user has submitted valid payment proof

#### 2. **Payment Verification Node** (`nodes.py`)

- Automatically detects payment screenshots in user messages
- Looks for:
  - Payment-related keywords: "paid", "transaction", "upi payment", "payment successful", "gpay", "phonepe", "paytm", "₹", "transfer", etc.
  - Image analysis results (images uploaded by user)
- Sets verification status globally using thread_id
- Runs automatically in the graph flow before conversation

#### 3. **Calendar Booking Tool** (`google_calendar_tools.py`)

- Modified `book_calendar_event` to check payment status BEFORE booking
- Retrieves thread_id from RunnableConfig
- Checks global `_payment_verification_state` dictionary
- Returns error message if payment not verified
- Proceeds with booking only if payment verified

#### 4. **Graph Integration** (`graph.py`)

- Added `payment_verification_node` to the graph flow
- Positioned after `pooja_injection_node` and before `memory_injection_node`
- Runs on every message to detect payment screenshots

#### 5. **Agent Instructions** (`prompts.py`)

- Updated `CHARACTER_CARD_PROMPT` with payment requirements
- Agent now knows to:
  - Request payment screenshot before booking
  - Guide users through payment process
  - Verify payment before attempting to book
  - Show QR code for payment

## User Flow

### Happy Path: With Payment Verification

1. **User**: "I want to book a consultation on Oct 5th at 2pm"
2. **Agent**: "Sure! To confirm your booking, please first share your payment screenshot. You can scan the QR code to make payment."
3. **User**: _uploads payment screenshot_
4. **System**: Payment verification node detects payment keywords + image → Sets `payment_verified = True`
5. **User**: "Here's my payment. Please book for Oct 5th at 2pm"
6. **Agent**: _Uses book_calendar_event tool_ → ✅ Booking successful!

### Rejection Path: Without Payment Verification

1. **User**: "Book appointment for Oct 5th at 2pm"
2. **Agent**: _Tries to use book_calendar_event tool_
3. **Tool**: ❌ Returns error: "Payment verification required before booking. Please send payment screenshot..."
4. **Agent**: Relays the error to user, asks for payment proof

## Technical Details

### Payment Detection Keywords

```python
payment_keywords = [
    "payment screenshot",
    "payment proof",
    "paid",
    "transaction",
    "upi payment",
    "payment successful",
    "payment done",
    "gpay",
    "phonepe",
    "paytm",
    "₹",
    "rupees",
    "amount transferred",
    "credited",
    "debited",
    "transfer"
]
```

### Verification Logic

```python
has_payment_keywords = any(keyword in message.lower() for keyword in payment_keywords)
has_image_analysis = "[Image Analysis:" in message.content

if has_payment_keywords and has_image_analysis:
    set_payment_verified(thread_id, True)
```

### Global State Storage

- Uses in-memory dictionary: `_payment_verification_state = {thread_id: bool}`
- Thread-safe for concurrent users
- Persists across messages within same thread
- Can be upgraded to database storage if needed

## Security Features

1. **Dual Verification**: Requires BOTH payment keywords AND image upload
2. **Per-User Tracking**: Each user (thread_id) has separate verification status
3. **Tool-Level Enforcement**: Booking tool independently checks payment status
4. **Cannot Be Bypassed**: Even if agent tries to book without payment, tool will reject

## Testing the Feature

### Test Case 1: Successful Booking with Payment

```
1. Upload an image with text mentioning "paid ₹500" or similar
2. Try to book: "Book consultation for Oct 5 at 2pm"
3. Expected: Booking should succeed
```

### Test Case 2: Booking Without Payment

```
1. Don't send any payment screenshot
2. Try to book: "Book consultation for Oct 5 at 2pm"
3. Expected: Tool returns error asking for payment screenshot
```

### Test Case 3: Image Without Payment Keywords

```
1. Upload a random image (not payment related)
2. Try to book
3. Expected: Tool returns error (payment not verified)
```

### Test Case 4: Payment Keywords Without Image

```
1. Send text: "I have paid ₹500"
2. Try to book
3. Expected: Tool returns error (requires image proof)
```

## Configuration

### Disabling Payment Verification (if needed)

To disable payment verification temporarily:

```python
# In google_calendar_tools.py, comment out the payment check:
# if not payment_verified:
#     return "Payment verification required..."
```

### Customizing Payment Keywords

Add more payment-related terms to the `payment_keywords` list in `payment_verification_node`.

### Changing Verification Logic

Modify the verification logic in `payment_verification_node` to:

- Require additional checks
- Use ML-based payment screenshot detection
- Integrate with payment gateway APIs

## Future Enhancements

1. **Database Storage**: Store payment verification in persistent DB instead of memory
2. **Payment Amount Verification**: Extract and verify payment amount from screenshot
3. **Payment Gateway Integration**: Integrate with actual payment gateway for real-time verification
4. **Multiple Payment Methods**: Support for different payment proof formats
5. **Payment History**: Track all payment screenshots and booking history per user
6. **Admin Dashboard**: View and verify payments manually if needed
7. **OCR Integration**: Use OCR to extract transaction details from screenshots
8. **Expiry**: Set expiry time for payment verification (e.g., 24 hours)

## Troubleshooting

### Payment not being detected

**Symptoms**: User uploads payment screenshot but agent still asks for payment

**Solutions**:

1. Check if message contains payment keywords
2. Verify image analysis is working (`[Image Analysis:` in content)
3. Check logs for "Payment screenshot detected" message
4. Ensure thread_id is being passed correctly

### Booking fails even after payment

**Symptoms**: Payment verified but booking still fails

**Solutions**:

1. Check if `set_payment_verified` was called
2. Verify thread_id matches between verification and booking
3. Check `_payment_verification_state` dictionary
4. Review logs for payment verification status

### False Positives

**Symptoms**: Random images being detected as payment screenshots

**Solutions**:

1. Tighten keyword matching (require more specific terms)
2. Add negative keywords to filter out non-payment images
3. Implement image classification ML model

## Files Modified

1. **src/ai_companion/graph/state.py**: Added `payment_verified` field
2. **src/ai_companion/graph/nodes.py**: Added `payment_verification_node`
3. **src/ai_companion/graph/graph.py**: Integrated payment node into graph
4. **src/ai_companion/modules/calendar/google_calendar_tools.py**:
   - Added payment verification check in `book_calendar_event`
   - Added `set_payment_verified` and `get_payment_verified` functions
5. **src/ai_companion/core/prompts.py**: Updated agent instructions about payment

## API Reference

### Functions

#### `set_payment_verified(thread_id: str, verified: bool = True)`

Sets payment verification status for a specific user/thread.

**Parameters:**

- `thread_id`: Unique identifier for user session
- `verified`: Boolean indicating payment status (default: True)

#### `get_payment_verified(thread_id: str) -> bool`

Checks if payment has been verified for a specific user/thread.

**Parameters:**

- `thread_id`: Unique identifier for user session

**Returns:**

- `bool`: True if payment verified, False otherwise

### State Fields

#### `payment_verified: bool`

Indicates whether the current user has submitted valid payment proof.

- Default: False
- Set to True by `payment_verification_node`
- Used by booking tool to gate appointments

# QR Code Image Feature

## Overview

The agent can now automatically send a QR code image to users when they ask for it. The feature works across both Chainlit and WhatsApp interfaces.

## How It Works

### 1. Detection

The agent detects QR code requests by looking for keywords in:

- User's message: `"qr"`, `"upi"`, `"scan"`
- Agent's response: `"qr"`, `"upi"`, `"payment options"`, `"payment karna"`, `"scan"`

### 2. Image Path Configuration

The QR code image path is configured in `settings.py`:

```python
UPI_QR_IMAGE_PATH: str | None = "img/QrCode.jpeg"
```

### 3. User Interaction Examples

Users can ask for the QR code in various ways:

- "Can you send me the QR code?"
- "Show me the payment QR"
- "I want to make a UPI payment"
- "Show me scan options"
- "How can I pay?"

### 4. How It Works Internally

1. **Conversation Node** (`nodes.py`):
   - Detects keywords in user message and agent response
   - Sets `attachment_image_path` in state if QR code should be sent
2. **State Management** (`state.py`):

   - Added `attachment_image_path` field to track when an image should be attached

3. **Chainlit Interface** (`interfaces/chainlit/app.py`):

   - Checks for `attachment_image_path` in output state
   - Displays the QR code image inline with the response

4. **WhatsApp Interface** (`interfaces/whatsapp/whatsapp_response.py`):
   - Already supported `attachment_image_path`
   - Sends QR code as an image message with caption

## Files Modified

1. **src/ai_companion/settings.py**: Updated QR code image path to `img/QrCode.jpeg`
2. **src/ai_companion/graph/state.py**: Added `attachment_image_path` field
3. **src/ai_companion/interfaces/chainlit/app.py**: Added QR code image display logic

## Testing

To test the feature:

### In Chainlit:

1. Start the Chainlit app
2. Send a message like "Can you send me the QR code?"
3. The agent will respond with text and display the QR code image inline

### In WhatsApp:

1. Send a message to your WhatsApp number
2. Ask for the QR code
3. The agent will send an image message with the QR code

## Customization

To use a different QR code image:

1. Add your image to the `img/` folder
2. Update the `UPI_QR_IMAGE_PATH` setting in `settings.py` or via environment variable:
   ```
   UPI_QR_IMAGE_PATH=img/your_qr_code.png
   ```

## Notes

- The feature uses relative paths from the project root
- The QR code is only sent when the setting `UPI_QR_IMAGE_PATH` is configured
- If the image file doesn't exist, the agent will send only the text response (graceful fallback)

from langgraph.graph import MessagesState
from typing import Optional


class AICompanionState(MessagesState):
    """Simplified state class for the unified AI Companion agent.

    Extends MessagesState to track conversation history and domain-specific context.
    Removes router-specific fields in favor of a single conversational agent that 
    naturally infers intent and uses tools as needed.

    Attributes:
        summary (str): Rolling conversation summary for context management
        audio_buffer (bytes): Audio buffer for speech-to-text conversion
        image_path (str): Path to generated images (if any)
        attachment_image_path (str): Path to attachments to send (e.g., QR codes)
        current_activity (str): Ava's current activity based on schedule
        apply_activity (bool): Whether to apply the current activity context
        memory_context (str): User-specific memories to inject into prompts
        product_context (str): Relevant product/service context detected from conversation (pooja, products, packages, services)
        intent_context (str): AI-classified intent and conversation stage context
        payment_verified (bool): Whether valid payment has been verified
        payment_amount (Optional[int]): Total payment amount verified (including split payments)
        payment_status (Optional[str]): Payment verification status (verified_full/partial_payment/verification_failed)
        payment_remaining (Optional[int]): Remaining amount for split payments
    """

    summary: str
    audio_buffer: bytes
    image_path: str
    attachment_image_path: str
    current_activity: str
    apply_activity: bool
    memory_context: str
    product_context: str
    intent_context: str
    payment_verified: bool
    
    # Payment verification details
    payment_amount: Optional[int]
    payment_status: Optional[str]
    payment_remaining: Optional[int]

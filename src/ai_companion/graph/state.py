from langgraph.graph import MessagesState
from typing import Optional


class AICompanionState(MessagesState):
    """Simplified state for the unified AI Companion agent (Google Cymbal pattern).

    Extends MessagesState to track conversation history and session-loaded context.
    All context is loaded upfront in load_session_context_node for efficiency.

    Attributes:
        summary (str): Rolling conversation summary for context management
        attachment_image_path (str): Path to attachments to send (e.g., QR codes)
        current_activity (str): Guru Maa's current activity/schedule (loaded from session)
        memory_context (str): User-specific memories (loaded from session)
        product_context (str): Relevant product/service context (loaded from session)
        payment_verified (bool): Whether valid payment has been verified
        payment_amount (Optional[int]): Total payment amount verified (including split payments)
        payment_status (Optional[str]): Payment verification status (verified_full/partial_payment/verification_failed)
        payment_remaining (Optional[int]): Remaining amount for split payments
    """

    summary: str
    attachment_image_path: str
    current_activity: str
    memory_context: str
    product_context: str
    payment_verified: bool
    
    # Payment verification details
    payment_amount: Optional[int]
    payment_status: Optional[str]
    payment_remaining: Optional[int]

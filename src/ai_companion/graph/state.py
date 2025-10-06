from langgraph.graph import MessagesState
from typing import Optional


class AICompanionState(MessagesState):
    """State class for the AI Companion workflow.

    Extends MessagesState to track conversation history and maintains the last message received.

    Attributes:
        last_message (AnyMessage): The most recent message in the conversation, can be any valid
            LangChain message type (HumanMessage, AIMessage, etc.)
        workflow (str): The current workflow the AI Companion is in. Can be "conversation", "image", or "audio".
        audio_buffer (bytes): The audio buffer to be used for speech-to-text conversion.
        current_activity (str): The current activity of Ava based on the schedule.
        memory_context (str): The context of the memories to be injected into the character card.
        payment_verified (bool): Whether the user has submitted a valid payment screenshot.
        
        # Enhanced routing fields:
        primary_intent (str): Primary intent detected by router (booking/consultation_inquiry/products_pooja/general)
        secondary_intent (Optional[str]): Secondary intent if hybrid intent detected
        confidence (float): Confidence score for intent classification (0.0 to 1.0)
        conversation_stage (str): Current stage in customer journey (inquiry/interested/payment_verified/etc.)
    """

    summary: str
    workflow: str
    audio_buffer: bytes
    image_path: str
    attachment_image_path: str
    current_activity: str
    apply_activity: bool
    memory_context: str
    pooja_context: str
    payment_verified: bool
    
    # Enhanced routing fields
    primary_intent: str
    secondary_intent: Optional[str]
    confidence: float
    conversation_stage: str

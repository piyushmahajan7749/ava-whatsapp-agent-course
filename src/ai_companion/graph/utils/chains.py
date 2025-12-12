from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from typing import Optional

from ai_companion.core.prompts import CHARACTER_CARD_PROMPT, INTENT_ROUTER_PROMPT
from ai_companion.core.knowledge import BUSINESS_KNOWLEDGE
from ai_companion.graph.utils.helpers import AsteriskRemovalParser, get_chat_model
from ai_companion.modules.calendar.google_calendar_tools import get_calendar_tools


class RouterResponse(BaseModel):
    """Enhanced router response with intent detection and conversation stage tracking."""
    
    # Media type routing (preserved from original)
    response_type: str = Field(
        description="The media response type. Must be one of: 'conversation', 'image', or 'audio'"
    )
    
    # Intent routing (new)
    primary_intent: str = Field(
        description="The primary intent of the user. Must be one of: 'booking', 'consultation_inquiry', 'products_pooja', 'general', 'escalation_needed'"
    )
    
    secondary_intent: Optional[str] = Field(
        default=None,
        description="Optional secondary intent if message contains multiple intents. Can be: 'booking', 'consultation_inquiry', 'products_pooja', 'general', 'escalation_needed', or None"
    )
    
    confidence: float = Field(
        description="Confidence score for the primary intent classification. Range: 0.0 to 1.0",
        ge=0.0,
        le=1.0
    )
    
    conversation_stage: str = Field(
        description="Current stage in customer journey. Must be one of: 'inquiry', 'interested', 'payment_pending', 'payment_verified', 'booking_ready', 'confirmed', 'general_chat', 'escalation_requested'"
    )
    
    reasoning: str = Field(
        description="Brief explanation of the routing decision (1-2 sentences)"
    )


def get_router_chain():
    """
    Get the enhanced intent-based router chain.
    
    Returns a chain that analyzes conversation context and returns:
    - Media type (conversation/audio/image)
    - Primary intent (booking/consultation_inquiry/products_pooja/general)
    - Secondary intent (if hybrid intent detected)
    - Confidence score
    - Conversation stage
    """
    model = get_chat_model(temperature=0.3).with_structured_output(RouterResponse)

    prompt = ChatPromptTemplate.from_messages(
        [("system", INTENT_ROUTER_PROMPT), MessagesPlaceholder(variable_name="messages")]
    )

    return prompt | model


def get_character_response_chain(
    summary: str = "", 
    enable_tools: bool = False,
    additional_context: str = ""
):
    """
    Get the character response chain with optional tool calling support (Google Cymbal pattern).
    
    Simplified from previous version - removed conversation_stage parameter in favor of
    natural intent inference by the LLM. All domain knowledge is now in UNIFIED_AGENT_INSTRUCTIONS.
    
    Args:
        summary: Conversation summary to include in the prompt
        enable_tools: If True, bind calendar tools to the model for tool calling
        additional_context: Unified agent instructions with all domain knowledge
    
    Returns:
        A chain that can generate character responses (with or without tool calls)
    """
    from langchain_core.runnables import RunnableLambda
    from datetime import datetime
    import pytz
    
    model = get_chat_model(temperature=0.7, max_tokens=120)  # Optimized for short, focused messages
    
    # Bind tools if enabled
    if enable_tools:
        tools = get_calendar_tools()
        model = model.bind_tools(tools)
    
    def format_system_message(inputs):
        """Format the system message with session context."""
        system_message = CHARACTER_CARD_PROMPT
        
        # Add current date/time context in IST
        ist = pytz.timezone('Asia/Kolkata')
        current_datetime = datetime.now(ist)
        system_message += (
            f"\n\nCurrent Date and Time (IST): {current_datetime.strftime('%A, %B %d, %Y at %I:%M %p IST')}\n"
            f"Timezone: Asia/Kolkata (IST - Indian Standard Time, UTC+5:30)\n"
            f"When interpreting relative dates like 'tomorrow', 'next week', etc., use this as the reference point.\n"
            f"IMPORTANT: All times should be interpreted as IST unless explicitly stated otherwise."
        )

        # Inject authoritative knowledge so LLM stays grounded
        system_message += (
            "\n\nAuthoritative Business Knowledge (ground truth; do not contradict):\n"
            f"{BUSINESS_KNOWLEDGE}\n"
            "If any user-provided info, memory, or retrieved context conflicts with this knowledge, "
            "politely correct it and adhere to the facts above.\n"
        )

        if summary:
            system_message += f"\n\nSummary of conversation earlier: {summary}"
        
        # Add session-loaded context (loaded by load_session_context_node)
        if inputs.get("current_activity"):
            system_message += f"\n\nCurrent Activity: {inputs['current_activity']}"
        
        if inputs.get("memory_context"):
            system_message += f"\n\nRelevant Memories: {inputs['memory_context']}"
        
        if inputs.get("product_context"):
            system_message += f"\n\nProduct Context: {inputs['product_context']}"

        # Force response language when requested by the caller (e.g., WhatsApp Hindi users).
        # This is more robust than relying on post-translation alone.
        response_language = (inputs.get("response_language") or "").strip().lower()
        if response_language == "hindi":
            system_message += (
                "\n\nLANGUAGE REQUIREMENT:\n"
                "- The user is writing in Hindi. Respond in Hindi (Devanagari script).\n"
                "- Keep it concise and end with a complete sentence.\n"
            )
        
        # Add unified agent instructions with all domain knowledge
        if additional_context:
            system_message += f"\n\n{additional_context}"
        
        if enable_tools:
            system_message += (
                "\n\nYou have access to calendar and business tools. Use the appropriate tools when needed:\n"
                "\n**CALENDAR TOOLS:**\n"
                "- check_calendar_availability: Check if a time slot is free\n"
                "- book_calendar_event: Book an event in the calendar\n"
                "- get_available_consultation_slots: Get all available slots for a specific date\n"
                "\n**BUSINESS TOOLS:**\n"
                "- log_product_order_to_sheets: Log product/puja orders to business spreadsheet\n"
                "\n**CRITICAL TIMEZONE INSTRUCTIONS:**\n"
                "- All times mentioned by users are in IST (Indian Standard Time, UTC+5:30)\n"
                "- When calling calendar tools, provide times in ISO format WITH IST offset\n"
                "- Example: For 10:00 AM IST on Oct 4, 2025, use: 2025-10-04T10:00:00+05:30\n"
                "- Example: For 3:30 PM IST on Oct 5, 2025, use: 2025-10-05T15:30:00+05:30\n"
                "- Always include the +05:30 offset in the ISO datetime string\n"
                "\n**PRODUCT ORDER LOGGING:**\n"
                "- When a customer completes a product order or puja booking, ALWAYS call log_product_order_to_sheets\n"
                "- This creates a business record for order fulfillment\n"
                "- Required fields: product_type, product_name, customer_name, payment_amount, shipping_address\n"
                "- Optional fields: gotra, contact_info, payment_details, puja_date, notes\n"
                "Always confirm details with the user before booking events or logging orders."
            )
        
        # Return formatted messages
        return [("system", system_message)] + inputs["messages"]
    
    # Create chain with dynamic system message
    format_messages = RunnableLambda(format_system_message)

    # Only apply AsteriskRemovalParser if tools are not enabled
    # (tool calls need raw AIMessage format)
    if enable_tools:
        return format_messages | model
    else:
        return format_messages | model | AsteriskRemovalParser()

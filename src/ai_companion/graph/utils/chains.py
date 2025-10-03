from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from ai_companion.core.prompts import CHARACTER_CARD_PROMPT, ROUTER_PROMPT
from ai_companion.core.knowledge import BUSINESS_KNOWLEDGE
from ai_companion.graph.utils.helpers import AsteriskRemovalParser, get_chat_model
from ai_companion.modules.calendar.google_calendar_tools import get_calendar_tools


class RouterResponse(BaseModel):
    response_type: str = Field(
        description="The response type to give to the user. It must be one of: 'conversation', 'image' or 'audio'"
    )


def get_router_chain():
    model = get_chat_model(temperature=0.3).with_structured_output(RouterResponse)

    prompt = ChatPromptTemplate.from_messages(
        [("system", ROUTER_PROMPT), MessagesPlaceholder(variable_name="messages")]
    )

    return prompt | model


def get_character_response_chain(summary: str = "", enable_tools: bool = False):
    """
    Get the character response chain with optional tool calling support.
    
    Args:
        summary: Conversation summary to include in the prompt
        enable_tools: If True, bind calendar tools to the model for tool calling
    
    Returns:
        A chain that can generate character responses (with or without tool calls)
    """
    from langchain_core.runnables import RunnableLambda
    from datetime import datetime
    import pytz
    
    model = get_chat_model()
    
    # Bind tools if enabled
    if enable_tools:
        tools = get_calendar_tools()
        model = model.bind_tools(tools)
    
    def format_system_message(inputs):
        """Format the system message with dynamic context."""
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
            system_message += f"\n\nSummary of conversation earlier between Ava and the user: {summary}"
        
        # Add dynamic context
        if inputs.get("current_activity"):
            system_message += f"\n\nCurrent Activity: {inputs['current_activity']}"
        
        if inputs.get("memory_context"):
            system_message += f"\n\nRelevant Memories: {inputs['memory_context']}"
        
        if inputs.get("pooja_context"):
            system_message += f"\n\nPooja Context: {inputs['pooja_context']}"
        
        if enable_tools:
            system_message += (
                "\n\nYou have access to calendar tools to check availability and book events. "
                "When users ask about scheduling, availability, or booking, use the appropriate tools:\n"
                "- check_calendar_availability: Check if a time slot is free\n"
                "- book_calendar_event: Book an event in the calendar\n"
                "\n**CRITICAL TIMEZONE INSTRUCTIONS:**\n"
                "- All times mentioned by users are in IST (Indian Standard Time, UTC+5:30)\n"
                "- When calling calendar tools, provide times in ISO format WITH IST offset\n"
                "- Example: For 10:00 AM IST on Oct 4, 2025, use: 2025-10-04T10:00:00+05:30\n"
                "- Example: For 3:30 PM IST on Oct 5, 2025, use: 2025-10-05T15:30:00+05:30\n"
                "- Always include the +05:30 offset in the ISO datetime string\n"
                "Always confirm details with the user before booking events."
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

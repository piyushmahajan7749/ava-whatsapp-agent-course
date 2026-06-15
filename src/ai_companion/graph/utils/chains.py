from ai_companion.core.prompts import CHARACTER_CARD_PROMPT
from ai_companion.core.knowledge import BUSINESS_KNOWLEDGE
from ai_companion.graph.utils.helpers import AsteriskRemovalParser, get_chat_model
from ai_companion.modules.saarthi.tools import get_saarthi_tools


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
    
    # 450 tokens: property-match messages carry 2-3 listings WITH links; plain
    # chat replies stay short via prompt instructions.
    model = get_chat_model(temperature=0.7, max_tokens=450)

    # Bind tools if enabled
    if enable_tools:
        tools = get_saarthi_tools()
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

        if inputs.get("lead_context"):
            system_message += f"\n\nLead CRM context (current state of THIS buyer — never re-ask what's here):\n{inputs['lead_context']}"

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
                "\n\nYou have CRM and property tools — use them per the journey instructions:\n"
                "- update_lead_requirements: save newly-learned buyer info (call silently, never narrate)\n"
                "- search_properties: find live matching listings with website links\n"
                "- schedule_property_visit: tentative site visit AFTER the buyer picked properties and gave availability\n"
                "- mark_lead_warm: flag a serious buyer / human-handoff request so a team member calls\n"
                "\n**TIMEZONE:** all user times are IST (UTC+5:30). When passing preferred_datetime_iso, "
                "use ISO format with offset, e.g. 2026-06-13T17:00:00+05:30, and it must be TOMORROW or later — never today."
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

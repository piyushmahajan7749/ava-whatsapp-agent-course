import os
import logging
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from ai_companion.graph.state import AICompanionState
from ai_companion.graph.utils.chains import (
    get_character_response_chain,
    get_router_chain,
)
from ai_companion.graph.utils.helpers import (
    get_chat_model,
    get_text_to_image_module,
    get_text_to_speech_module,
)
from ai_companion.modules.memory.long_term.memory_manager import get_memory_manager
from ai_companion.modules.schedules.context_generation import ScheduleContextGenerator
from ai_companion.modules.calendar.google_calendar_tools import (
    get_calendar_tools,
    set_payment_verified,
    get_payment_verified,
)
from ai_companion.settings import settings
from ai_companion.modules.pooja.data import find_pooja_by_text, format_pooja_context
"""Conversation and workflow nodes."""


logger = logging.getLogger(__name__)


async def router_node(state: AICompanionState):
    """
    Route the conversation to appropriate workflow (conversation/image/audio).
    
    Filters out tool-related messages since router doesn't need them.
    """
    from langchain_core.messages import ToolMessage
    
    # Filter out tool calls and tool messages for the router
    # Router only needs to see human messages and regular AI responses
    messages_for_router = []
    for msg in state["messages"][-settings.ROUTER_MESSAGES_TO_ANALYZE :]:
        # Skip tool messages
        if isinstance(msg, ToolMessage):
            continue
        # Skip AI messages that only contain tool calls (no actual text)
        if isinstance(msg, AIMessage) and msg.tool_calls and not msg.content:
            continue
        messages_for_router.append(msg)
    
    chain = get_router_chain()
    response = await chain.ainvoke({"messages": messages_for_router})
    return {"workflow": response.response_type}


def context_injection_node(state: AICompanionState):
    schedule_context = ScheduleContextGenerator.get_current_activity()
    if schedule_context != state.get("current_activity", ""):
        apply_activity = True
    else:
        apply_activity = False
    return {"apply_activity": apply_activity, "current_activity": schedule_context}


def pooja_injection_node(state: AICompanionState):
    """Detect and inject relevant pooja context based on recent user messages."""
    recent_text = " ".join([m.content for m in state["messages"][-3:]]) if state.get("messages") else ""
    pooja = find_pooja_by_text(recent_text)
    context = format_pooja_context(pooja) if pooja else ""
    return {"pooja_context": context}


def payment_verification_node(state: AICompanionState, config: RunnableConfig):
    """
    Detect and verify payment screenshots from user images.
    
    Checks the last user message for payment-related keywords and image analysis.
    If a payment screenshot is detected, sets payment_verified to True.
    """
    if not state.get("messages"):
        return {}
    
    last_message = state["messages"][-1]
    content_lower = last_message.content.lower() if last_message.content else ""
    
    # Check for payment screenshot indicators
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
    
    # Check if message contains payment-related content
    has_payment_keywords = any(keyword in content_lower for keyword in payment_keywords)
    
    # Check for image analysis indicating a payment screenshot
    has_image_analysis = "[Image Analysis:" in last_message.content
    
    # Get thread_id from config
    thread_id = config.get("configurable", {}).get("thread_id") if config else None
    
    if has_payment_keywords and has_image_analysis and thread_id:
        logger.info(f"Payment screenshot detected and verified for thread {thread_id}")
        set_payment_verified(thread_id, True)
        return {"payment_verified": True}
    
    return {}


async def conversation_node(state: AICompanionState, config: RunnableConfig):
    """
    Handle conversation with tool calling support.
    
    This node can either:
    1. Generate a text response
    2. Make tool calls (if user asks about calendar/scheduling)
    """
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    pooja_context = state.get("pooja_context", "")

    # Begin grounded LLM path (policy short-circuit removed)
    logger.debug(
        "conversation_node: begin; messages=%d, has_memory=%s, has_pooja=%s",
        len(state.get("messages", [])),
        bool(memory_context),
        bool(pooja_context),
    )

    # Enable tools for calendar-related queries
    # You can make this smarter by detecting calendar intent in router if needed
    enable_tools = True  # Always enable tools; LLM will decide when to use them
    
    chain = get_character_response_chain(state.get("summary", ""), enable_tools=enable_tools)

    logger.debug("conversation_node: invoking character chain (tools_enabled=%s)", enable_tools)
    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "current_activity": current_activity,
            "memory_context": memory_context,
            "pooja_context": pooja_context,
        },
        config,
    )
    logger.debug("conversation_node: character chain completed")

    # Check if response contains tool calls
    if isinstance(response, AIMessage) and response.tool_calls:
        logger.info(f"Tool calls detected: {[tc['name'] for tc in response.tool_calls]}")
        # Return the AIMessage with tool calls (tools_node will execute them)
        return {"messages": [response]}
    
    # Regular text response handling
    # When tools are enabled, response is always AIMessage
    if isinstance(response, AIMessage):
        response_text = response.content
        # Return the AIMessage as-is to preserve message structure
        out = {"messages": [response]}
    else:
        # When tools are disabled, response is a string
        response_text = response
        out = {"messages": [AIMessage(content=response_text)]}
    
    # If user asked for QR / payment options, attach image path hint for transport layer
    lower_resp = response_text.lower() if isinstance(response_text, str) else str(response_text).lower()
    attach_qr = any(k in lower_resp for k in ["qr", "upi", "payment options", "payment karna", "scan"]) or any(
        k in (state["messages"][-1].content.lower() if state.get("messages") else "") for k in ["qr", "upi", "scan"]
    )

    if attach_qr and getattr(settings, "UPI_QR_IMAGE_PATH", None):
        out["attachment_image_path"] = settings.UPI_QR_IMAGE_PATH
    return out


async def image_node(state: AICompanionState, config: RunnableConfig):
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    pooja_context = state.get("pooja_context", "")

    chain = get_character_response_chain(state.get("summary", ""))
    text_to_image_module = get_text_to_image_module()

    scenario = await text_to_image_module.create_scenario(state["messages"][-5:])
    os.makedirs("generated_images", exist_ok=True)
    img_path = f"generated_images/image_{str(uuid4())}.png"
    await text_to_image_module.generate_image(scenario.image_prompt, img_path)

    # Inject the image prompt information as an AI message
    scenario_message = HumanMessage(content=f"<image attached by Ava generated from prompt: {scenario.image_prompt}>")
    updated_messages = state["messages"] + [scenario_message]

    response = await chain.ainvoke(
        {
            "messages": updated_messages,
            "current_activity": current_activity,
            "memory_context": memory_context,
            "pooja_context": pooja_context,
        },
        config,
    )

    return {"messages": AIMessage(content=response), "image_path": img_path}


async def audio_node(state: AICompanionState, config: RunnableConfig):
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    pooja_context = state.get("pooja_context", "")

    chain = get_character_response_chain(state.get("summary", ""))
    text_to_speech_module = get_text_to_speech_module()

    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "current_activity": current_activity,
            "memory_context": memory_context,
            "pooja_context": pooja_context,
        },
        config,
    )
    output_audio = await text_to_speech_module.synthesize(response)

    return {"messages": response, "audio_buffer": output_audio}


async def summarize_conversation_node(state: AICompanionState):
    model = get_chat_model()
    summary = state.get("summary", "")

    if summary:
        summary_message = (
            f"This is summary of the conversation to date between Ava and the user: {summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )
    else:
        summary_message = (
            "Create a summary of the conversation above between Ava and the user. "
            "The summary must be a short description of the conversation so far, "
            "but that captures all the relevant information shared between Ava and the user:"
        )

    messages = state["messages"] + [HumanMessage(content=summary_message)]
    response = await model.ainvoke(messages)

    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][: -settings.TOTAL_MESSAGES_AFTER_SUMMARY]]
    return {"summary": response.content, "messages": delete_messages}


async def memory_extraction_node(state: AICompanionState):
    """Extract and store important information from the last message."""
    if not state["messages"]:
        return {}

    memory_manager = get_memory_manager()
    await memory_manager.extract_and_store_memories(state["messages"][-1])
    return {}


def memory_injection_node(state: AICompanionState):
    """Retrieve and inject relevant memories into the character card."""
    memory_manager = get_memory_manager()

    # Get relevant memories based on recent conversation
    recent_context = " ".join([m.content for m in state["messages"][-3:]])
    memories = memory_manager.get_relevant_memories(recent_context)

    # Format memories for the character card
    memory_context = memory_manager.format_memories_for_prompt(memories)

    return {"memory_context": memory_context}


# Create the tools node for executing tool calls
tools_node = ToolNode(get_calendar_tools())

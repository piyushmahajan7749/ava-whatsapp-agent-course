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
    add_payment_amount,
    get_payment_total,
    clear_payment_history,
)
from ai_companion.settings import settings
from ai_companion.modules.pooja.data import find_pooja_by_text, format_pooja_context
"""Conversation and workflow nodes."""


logger = logging.getLogger(__name__)


async def router_node(state: AICompanionState):
    """
    Enhanced router with intent detection and conversation stage tracking.
    
    Routes based on:
    - Media type (conversation/audio/image)
    - Primary intent (booking/consultation_inquiry/products_pooja/general)
    - Secondary intent (if hybrid intent detected)
    - Conversation stage (inquiry/interested/payment_verified/etc.)
    
    Filters out tool-related messages since router doesn't need them.
    """
    from langchain_core.messages import ToolMessage
    
    # Edge case: Handle empty message history
    if not state.get("messages"):
        logger.warning("Router called with empty message history, using defaults")
        return {
            "workflow": "conversation",
            "primary_intent": "general",
            "secondary_intent": None,
            "confidence": 1.0,
            "conversation_stage": "inquiry",
        }
    
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
    
    # Edge case: All messages filtered out (only tool messages)
    if not messages_for_router:
        logger.warning("All messages filtered out (tool messages only), using defaults")
        return {
            "workflow": "conversation",
            "primary_intent": "general",
            "secondary_intent": None,
            "confidence": 0.8,
            "conversation_stage": "general_chat",
        }
    
    chain = get_router_chain()
    response = await chain.ainvoke({"messages": messages_for_router})
    
    # Log routing decision for debugging
    logger.info(
        f"Router Decision - Media: {response.response_type}, "
        f"Intent: {response.primary_intent} (secondary: {response.secondary_intent}), "
        f"Stage: {response.conversation_stage}, "
        f"Confidence: {response.confidence:.2f}, "
        f"Reasoning: {response.reasoning}"
    )
    
    return {
        "workflow": response.response_type,
        "primary_intent": response.primary_intent,
        "secondary_intent": response.secondary_intent,
        "confidence": response.confidence,
        "conversation_stage": response.conversation_stage,
    }


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


async def payment_verification_node(state: AICompanionState, config: RunnableConfig):
    """
    Detect and verify payment screenshots from user images using Azure Vision AI.
    
    Uses comprehensive PaymentVerifier to:
    1. Detect if image contains payment information
    2. Extract payment amount
    3. Verify amount matches expected consultation fee (₹2,100)
    4. Extract transaction details (ID, date, UPI app)
    5. Calculate confidence score
    
    Sets payment_verified to True if valid payment detected with sufficient confidence.
    """
    from ai_companion.modules.payment import PaymentVerifier
    
    if not state.get("messages"):
        return {}
    
    last_message = state["messages"][-1]
    content_lower = last_message.content.lower() if last_message.content else ""
    
    # Get thread_id from config
    thread_id = config.get("configurable", {}).get("thread_id") if config else None
    
    # Check for payment-related keywords in message
    payment_keywords = [
        "payment", "paid", "transaction", "upi", "gpay", "phonepe", "paytm",
        "screenshot", "proof", "₹", "rupees", "transfer", "successful"
    ]
    has_payment_keywords = any(keyword in content_lower for keyword in payment_keywords)
    
    # Check if message contains image data (look for image analysis marker)
    has_image = "[Image Analysis:" in last_message.content
    
    # If potential payment screenshot detected, verify it
    if has_payment_keywords and has_image and thread_id:
        try:
            logger.info(f"🔍 Potential payment screenshot detected for thread {thread_id}, verifying with AI...")
            
            # Initialize payment verifier
            verifier = PaymentVerifier()
            
            # Extract existing image analysis text
            if "[Image Analysis:" in last_message.content:
                start_idx = last_message.content.find("[Image Analysis:")
                end_idx = last_message.content.find("]", start_idx)
                if end_idx > start_idx:
                    image_analysis = last_message.content[start_idx+len("[Image Analysis:"):end_idx].strip()
                    
                    # Verify payment from the image analysis text
                    payment_details = verifier.verify_from_text_analysis(image_analysis)
                    
                    # Log verification results
                    logger.info(
                        f"Payment Verification Results for thread {thread_id}:\n"
                        f"  Valid: {payment_details.is_valid}\n"
                        f"  Amount: ₹{payment_details.amount}\n"
                        f"  Status: {payment_details.status}\n"
                        f"  App: {payment_details.app}\n"
                        f"  Amount Matches: {payment_details.amount_matches}\n"
                        f"  Confidence: {payment_details.confidence:.2f}\n"
                        f"  Notes: {payment_details.notes}"
                    )
                    
                    # Handle split payments - check if amount detected
                    if payment_details.amount and payment_details.amount > 0:
                        # Add this payment to history
                        payment_summary = add_payment_amount(thread_id, payment_details.amount)
                        
                        logger.info(
                            f"💰 Payment recorded for thread {thread_id}:\n"
                            f"  This payment: ₹{payment_details.amount}\n"
                            f"  Total paid: ₹{payment_summary['total']}\n"
                            f"  Payments: {payment_summary['payments']}\n"
                            f"  Remaining: ₹{payment_summary['remaining']}"
                        )
                        
                        # Decision logic based on total amount
                        if payment_summary['fully_paid']:
                            # Full amount received (including split payments)
                            logger.info(
                                f"✅ FULL PAYMENT VERIFIED for thread {thread_id}:\n"
                                f"  Total: ₹{payment_summary['total']} from {payment_summary['count']} payment(s)\n"
                                f"  Payments: {payment_summary['payments']}\n"
                                f"  Status: {payment_details.status}"
                            )
                            set_payment_verified(thread_id, True)
                            
                            return {
                                "payment_verified": True,
                                "payment_amount": payment_summary['total'],
                                "payment_status": "verified_full"
                            }
                        
                        else:
                            # Partial payment - need more
                            logger.info(
                                f"📊 PARTIAL PAYMENT for thread {thread_id}:\n"
                                f"  Paid so far: ₹{payment_summary['total']}\n"
                                f"  Still needed: ₹{payment_summary['remaining']}\n"
                                f"  Payments received: {payment_summary['payments']}"
                            )
                            
                            return {
                                "payment_verified": False,
                                "payment_amount": payment_summary['total'],
                                "payment_status": "partial_payment",
                                "payment_remaining": payment_summary['remaining']
                            }
                    
                    else:
                        # No amount detected or low confidence
                        logger.warning(
                            f"⚠️  Payment verification UNCERTAIN for thread {thread_id}: "
                            f"Confidence too low ({payment_details.confidence:.2f}) or no amount detected"
                        )
                        
                        return {
                            "payment_verified": False,
                            "payment_status": "verification_failed"
                        }
            
            # Fallback: Basic verification (backward compatibility)
            logger.info(f"Using fallback verification for thread {thread_id}")
            amount_indicators = ["2100", "2,100", "₹2100", "₹2,100", "Rs 2100", "Rs.2100"]
            success_indicators = ["success", "successful", "completed", "done", "credited"]
            
            has_correct_amount = any(amount in last_message.content for amount in amount_indicators)
            has_success_status = any(status in content_lower for status in success_indicators)
            
            if has_correct_amount and has_success_status:
                logger.info(f"✅ Payment verified (fallback) for thread {thread_id}")
                set_payment_verified(thread_id, True)
                return {
                    "payment_verified": True,
                    "payment_amount": 2100,
                    "payment_status": "verified_fallback"
                }
            
        except Exception as e:
            logger.error(f"Error during payment verification for thread {thread_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't fail the flow, just log and continue
    
    return {}


async def conversation_node(state: AICompanionState, config: RunnableConfig):
    """
    Handle conversation with dynamic context loading based on intent.
    
    This node:
    1. Detects user's intent (from router)
    2. Loads appropriate context sections (booking/consultation/products/general/escalation)
    3. Handles hybrid intents (loads multiple contexts)
    4. Dynamically enables tools based on intent
    5. Maintains conversation continuity
    """
    from ai_companion.core.prompts import (
        BOOKING_CONTEXT,
        CONSULTATION_INQUIRY_CONTEXT,
        PRODUCTS_POOJA_CONTEXT,
        GENERAL_CONTEXT,
        ESCALATION_CONTEXT,
    )
    
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    pooja_context = state.get("pooja_context", "")
    
    # Get intent and stage from router
    primary_intent = state.get("primary_intent", "general")
    secondary_intent = state.get("secondary_intent")
    conversation_stage = state.get("conversation_stage", "inquiry")
    confidence = state.get("confidence", 0.5)

    logger.debug(
        "conversation_node: begin; messages=%d, intent=%s (secondary=%s), stage=%s, confidence=%.2f",
        len(state.get("messages", [])),
        primary_intent,
        secondary_intent,
        conversation_stage,
        confidence,
    )
    
    # TODO: Future enhancement - Add confidence threshold handling
    # if confidence < 0.4:
    #     # Ask clarifying question instead of proceeding with uncertain intent
    #     clarifying_prompt = "I want to make sure I understand correctly. Are you asking about..."
    #     return {"messages": [AIMessage(content=clarifying_prompt)]}
    #
    # This would improve accuracy for ambiguous queries

    # ============= DYNAMIC CONTEXT LOADING =============
    # Build context sections based on detected intent(s)
    context_sections = []
    enable_tools = False
    
    # Primary intent context
    if primary_intent == "escalation_needed":
        # PRIORITY: Escalation overrides everything
        context_sections.append(ESCALATION_CONTEXT)
        enable_tools = False  # NEVER enable tools during escalation
        logger.info("🚨 ESCALATION DETECTED - Loading ESCALATION_CONTEXT, tools disabled")
    elif primary_intent == "booking":
        context_sections.append(BOOKING_CONTEXT)
        enable_tools = True  # Enable calendar tools for booking
        logger.debug("Loaded BOOKING_CONTEXT, tools enabled")
    elif primary_intent == "consultation_inquiry":
        context_sections.append(CONSULTATION_INQUIRY_CONTEXT)
        logger.debug("Loaded CONSULTATION_INQUIRY_CONTEXT")
    elif primary_intent == "products_pooja":
        context_sections.append(PRODUCTS_POOJA_CONTEXT)
        logger.debug("Loaded PRODUCTS_POOJA_CONTEXT")
    else:  # general
        context_sections.append(GENERAL_CONTEXT)
        logger.debug("Loaded GENERAL_CONTEXT")
    
    # Secondary intent context (for hybrid intents)
    if secondary_intent:
        logger.debug(f"Hybrid intent detected, adding secondary context: {secondary_intent}")
        # If escalation is secondary intent, it should still take priority
        if secondary_intent == "escalation_needed" and primary_intent != "escalation_needed":
            logger.warning("Escalation detected as secondary intent - consider escalating")
            # Don't override primary context but note the escalation concern
        elif secondary_intent == "booking" and primary_intent != "booking" and primary_intent != "escalation_needed":
            context_sections.append(BOOKING_CONTEXT)
            enable_tools = True  # Enable tools if booking is mentioned (unless escalation is primary)
        elif secondary_intent == "consultation_inquiry" and primary_intent != "consultation_inquiry":
            context_sections.append(CONSULTATION_INQUIRY_CONTEXT)
        elif secondary_intent == "products_pooja" and primary_intent != "products_pooja":
            context_sections.append(PRODUCTS_POOJA_CONTEXT)
    
    # Combine all context sections
    additional_context = "\n\n---\n\n".join(context_sections)
    # ===================================================
    
    chain = get_character_response_chain(
        summary=state.get("summary", ""),
        enable_tools=enable_tools,
        additional_context=additional_context,
        conversation_stage=conversation_stage,
    )

    logger.debug("conversation_node: invoking character chain (tools_enabled=%s, contexts=%d)", 
                 enable_tools, len(context_sections))
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
    """
    Generate and return an image based on conversation context.
    
    Note: Image generation typically doesn't need specialized intent context,
    but we include it for consistency and future flexibility.
    """
    from ai_companion.core.prompts import GENERAL_CONTEXT
    
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    pooja_context = state.get("pooja_context", "")
    conversation_stage = state.get("conversation_stage", "general_chat")

    # Use general context for image generation
    chain = get_character_response_chain(
        summary=state.get("summary", ""),
        enable_tools=False,
        additional_context=GENERAL_CONTEXT,
        conversation_stage=conversation_stage,
    )
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
    """
    Generate and return an audio response based on conversation context.
    
    Uses intent-based context to provide appropriate audio responses.
    """
    from ai_companion.core.prompts import (
        BOOKING_CONTEXT,
        CONSULTATION_INQUIRY_CONTEXT,
        PRODUCTS_POOJA_CONTEXT,
        GENERAL_CONTEXT,
    )
    
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    pooja_context = state.get("pooja_context", "")
    
    # Get intent from state to provide appropriate context in audio response
    primary_intent = state.get("primary_intent", "general")
    conversation_stage = state.get("conversation_stage", "general_chat")
    
    # Load appropriate context based on intent
    context_map = {
        "booking": BOOKING_CONTEXT,
        "consultation_inquiry": CONSULTATION_INQUIRY_CONTEXT,
        "products_pooja": PRODUCTS_POOJA_CONTEXT,
        "general": GENERAL_CONTEXT,
    }
    additional_context = context_map.get(primary_intent, GENERAL_CONTEXT)

    chain = get_character_response_chain(
        summary=state.get("summary", ""),
        enable_tools=False,  # No tools in audio responses
        additional_context=additional_context,
        conversation_stage=conversation_stage,
    )
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


async def memory_extraction_node(state: AICompanionState, config: RunnableConfig):
    """Extract and store important information from the last message with user context.
    
    Args:
        state: Current conversation state
        config: Runnable config containing thread_id (user's phone number)
    """
    if not state["messages"]:
        return {}

    memory_manager = get_memory_manager()
    
    # Get user_id from thread_id (phone number)
    thread_id = config.get("configurable", {}).get("thread_id") if config else None
    
    # Extract and store memories with user context
    await memory_manager.extract_and_store_memories(state["messages"][-1], user_id=thread_id)
    
    logger.debug(f"Memory extraction complete for user: {thread_id}")
    return {}


def memory_injection_node(state: AICompanionState, config: RunnableConfig):
    """Retrieve and inject relevant user-specific memories into the character card.
    
    Args:
        state: Current conversation state
        config: Runnable config containing thread_id (user's phone number)
    """
    memory_manager = get_memory_manager()

    # Get user_id from thread_id (phone number)
    thread_id = config.get("configurable", {}).get("thread_id") if config else None

    # Get relevant memories based on recent conversation, filtered by user
    recent_context = " ".join([m.content for m in state["messages"][-3:]])
    memories = memory_manager.get_relevant_memories(recent_context, user_id=thread_id)

    # Format memories for the character card
    memory_context = memory_manager.format_memories_for_prompt(memories)
    
    logger.debug(f"Memory injection complete for user {thread_id}: {len(memories)} memories retrieved")

    return {"memory_context": memory_context}


# Create the tools node for executing tool calls
tools_node = ToolNode(get_calendar_tools())

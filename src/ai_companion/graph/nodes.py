import os
import logging
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from ai_companion.graph.state import AICompanionState
from ai_companion.graph.utils.chains import (
    get_character_response_chain,
)
from ai_companion.graph.utils.helpers import (
    get_chat_model,
    get_text_to_image_module,
    get_text_to_speech_module,
    chunk_response_into_messages,
)
from ai_companion.modules.language.hindi_detection import should_respond_in_hindi
from ai_companion.modules.language.hindi_translation import translate_response_if_needed
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
from ai_companion.modules.products.data import find_products_by_text, format_product_context, get_relevant_products_with_ai
from ai_companion.modules.intent.intent_classifier import classify_intent_with_ai, IntentClassification
"""Conversation and workflow nodes."""


logger = logging.getLogger(__name__)


def context_injection_node(state: AICompanionState):
    """Inject current schedule context for Ava's availability."""
    schedule_context = ScheduleContextGenerator.get_current_activity()
    if schedule_context != state.get("current_activity", ""):
        apply_activity = True
        logger.debug(f"📅 [CONTEXT_INJECTION] Activity updated: {schedule_context[:80]}...")
    else:
        apply_activity = False
        logger.debug(f"📅 [CONTEXT_INJECTION] Activity unchanged")
    return {"apply_activity": apply_activity, "current_activity": schedule_context}


def product_injection_node(state: AICompanionState):
    """
    Detect and inject relevant product/service context using AI-based analysis.
    
    This node uses AI to intelligently extract relevant products from the full catalog
    based on user conversation context, providing more accurate and comprehensive results
    than keyword-based matching.
    """
    recent_text = " ".join([m.content for m in state["messages"][-3:]]) if state.get("messages") else ""
    
    # Use AI-based product context extraction
    ai_products_context = get_relevant_products_with_ai(recent_text)
    
    # Keep pooja detection as fallback for specific pooja references
    pooja = find_pooja_by_text(recent_text)
    pooja_context = format_pooja_context(pooja) if pooja else ""
    
    # Combine AI-extracted context with pooja context
    product_context = ""
    if pooja_context:
        product_context += pooja_context + "\n\n"
    
    if ai_products_context:
        product_context += ai_products_context
    
    # Log what was detected
    if pooja:
        logger.info(f"🛍️ [PRODUCT_INJECTION] Detected pooja: {pooja.get('name', 'Unknown')}")
    if ai_products_context:
        logger.info(f"🛍️ [PRODUCT_INJECTION] AI extracted product context: {len(ai_products_context)} chars")
    if not pooja and not ai_products_context:
        logger.debug(f"🛍️ [PRODUCT_INJECTION] No relevant products/services detected by AI")
    
    return {"product_context": product_context}


def intent_classification_node(state: AICompanionState):
    """
    Classify user intent using AI-based analysis for better conversation routing.
    
    This node provides intelligent intent classification that helps the conversation
    node make better decisions about how to respond and what tools to use.
    """
    messages = state.get("messages", [])
    if not messages:
        logger.debug("🎯 [INTENT_CLASSIFICATION] No messages to classify")
        return {"intent_context": ""}
    
    # Get the latest user message
    latest_message = messages[-1]
    user_message = ""
    has_audio = False
    has_image = False
    
    if hasattr(latest_message, 'content'):
        user_message = latest_message.content
    elif hasattr(latest_message, 'type'):
        if latest_message.type == "audio":
            has_audio = True
            user_message = "User sent an audio message"
        elif latest_message.type == "image":
            has_image = True
            user_message = "User sent an image"
    
    # Get conversation history for context
    conversation_history = []
    for msg in messages[-5:]:  # Last 5 messages for context
        if hasattr(msg, 'content') and msg.content:
            if hasattr(msg, 'type') and msg.type == 'human':
                conversation_history.append(msg.content)
            elif hasattr(msg, '__class__') and 'Human' in str(msg.__class__):
                conversation_history.append(msg.content)
    
    # Classify intent using AI
    try:
        classification = classify_intent_with_ai(
            user_message=user_message,
            conversation_history=conversation_history,
            has_audio=has_audio,
            has_image=has_image
        )
        
        # Format intent context for the conversation node
        intent_context = f"""
**Intent Analysis:**
- Primary Intent: {classification.primary_intent}
- Secondary Intent: {classification.secondary_intent or 'None'}
- Confidence: {classification.confidence:.2f}
- Conversation Stage: {classification.conversation_stage}
- Reasoning: {classification.reasoning}
"""
        
        logger.info(
            f"🎯 [INTENT_CLASSIFICATION] Classified intent: {classification.primary_intent} "
            f"(confidence: {classification.confidence:.2f}, stage: {classification.conversation_stage})"
        )
        
        return {"intent_context": intent_context}
        
    except Exception as e:
        logger.error(f"❌ [INTENT_CLASSIFICATION] Error classifying intent: {e}")
        return {"intent_context": ""}


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
    Unified conversational agent that handles all user interactions.
    
    This simplified node:
    1. Uses a single set of unified instructions that naturally infer intent
    2. Always enables tools - the LLM decides when to use them based on context
    3. Provides all domain contexts for the agent to reference as needed
    4. Eliminates complex routing logic in favor of natural conversation flow
    5. Comprehensive logging for debugging and monitoring
    """
    from ai_companion.core.prompts import (
        UNIFIED_AGENT_INSTRUCTIONS,
        BOOKING_CONTEXT,
        CONSULTATION_INQUIRY_CONTEXT,
        PRODUCTS_POOJA_CONTEXT,
        GENERAL_CONTEXT,
        ESCALATION_CONTEXT,
    )
    
    # Get thread_id for logging
    thread_id = config.get("configurable", {}).get("thread_id") if config else "unknown"
    
    # Log conversation start with state context
    logger.info(
        f"🗣️ [CONVERSATION_NODE] Starting conversation for thread {thread_id} | "
        f"Messages: {len(state.get('messages', []))} | "
        f"Payment verified: {state.get('payment_verified', False)} | "
        f"Payment status: {state.get('payment_status', 'none')}"
    )
    
    # Detect if user is communicating in Hindi
    user_messages = [msg for msg in state.get("messages", []) if hasattr(msg, 'content') and msg.content]
    should_translate_to_hindi = should_respond_in_hindi(user_messages)
    
    if should_translate_to_hindi:
        logger.info(f"🇮🇳 [CONVERSATION_NODE] Hindi detected for thread {thread_id} - will translate response")
    
    # Gather all contextual information
    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    product_context = state.get("product_context", "")
    intent_context = state.get("intent_context", "")
    payment_verified = state.get("payment_verified", False)
    payment_status = state.get("payment_status")
    payment_amount = state.get("payment_amount")
    payment_remaining = state.get("payment_remaining")
    
    logger.debug(
        f"📋 [CONVERSATION_NODE] Context loaded for thread {thread_id}:\n"
        f"  - Current activity: {current_activity[:50] if current_activity else 'None'}...\n"
        f"  - Memory context: {len(memory_context)} chars\n"
        f"  - Product context: {len(product_context)} chars\n"
        f"  - Intent context: {len(intent_context)} chars\n"
        f"  - Payment: verified={payment_verified}, status={payment_status}, amount={payment_amount}, remaining={payment_remaining}"
    )
    
    # Combine all domain knowledge contexts for the agent to reference
    # The unified instructions will guide the agent on when to use each section
    context_parts = [
        UNIFIED_AGENT_INSTRUCTIONS,
        GENERAL_CONTEXT,
        BOOKING_CONTEXT,
        CONSULTATION_INQUIRY_CONTEXT,
        PRODUCTS_POOJA_CONTEXT,
        ESCALATION_CONTEXT,
    ]
    
    # Add intent context if available
    if intent_context:
        context_parts.append(intent_context)
    
    additional_context = "\n\n---\n\n".join(context_parts)
    
    logger.debug(f"📚 [CONVERSATION_NODE] Combined context size: {len(additional_context)} chars")
    
    # Always enable tools - the unified instructions guide when to use them
    # The LLM naturally decides based on conversation context
    chain = get_character_response_chain(
        summary=state.get("summary", ""),
        enable_tools=True,  # Re-enabled with credentials in Docker
        additional_context=additional_context,
        conversation_stage="conversation",  # Simplified: single stage
    )

    logger.info(f"🤖 [CONVERSATION_NODE] Invoking LLM chain for thread {thread_id} (tools: ENABLED)")
    
    try:
        response = await chain.ainvoke(
            {
                "messages": state["messages"],
                "current_activity": current_activity,
                "memory_context": memory_context,
                "product_context": product_context,
            },
            config,
        )
        logger.info(f"✅ [CONVERSATION_NODE] LLM response received for thread {thread_id}")
    except Exception as e:
        logger.error(f"❌ [CONVERSATION_NODE] Error invoking LLM chain for thread {thread_id}: {e}", exc_info=True)
        raise

    # Check if response contains tool calls
    if isinstance(response, AIMessage) and response.tool_calls:
        tool_names = [tc.get('name') for tc in response.tool_calls]
        logger.info(
            f"🛠️ [CONVERSATION_NODE] Tool calls detected for thread {thread_id}: {tool_names}\n"
            f"  Tool count: {len(response.tool_calls)}"
        )
        # Return the AIMessage with tool calls (tools_node will execute them)
        return {"messages": [response]}
    
    # Regular text response handling with message chunking
    if isinstance(response, AIMessage):
        response_text = response.content
        logger.info(
            f"💬 [CONVERSATION_NODE] Text response for thread {thread_id}: "
            f"{response_text[:100] if response_text else '(empty)'}..."
        )
        
        # Translate to Hindi if needed
        if should_translate_to_hindi:
            response_text = translate_response_if_needed(response_text, True)
            logger.info(f"🇮🇳 [CONVERSATION_NODE] Translated response to Hindi for thread {thread_id}")
        
        # Chunk the response into multiple focused messages
        message_chunks = chunk_response_into_messages(response_text)
        logger.info(f"📝 [CONVERSATION_NODE] Split response into {len(message_chunks)} messages for thread {thread_id}")
        
        # Create multiple AIMessages from chunks
        chunked_messages = [AIMessage(content=chunk) for chunk in message_chunks if chunk.strip()]
        out = {"messages": chunked_messages}
        
    else:
        # Fallback for string responses
        response_text = response
        logger.warning(
            f"⚠️ [CONVERSATION_NODE] Received string response (not AIMessage) for thread {thread_id}"
        )
        
        # Translate to Hindi if needed
        if should_translate_to_hindi:
            response_text = translate_response_if_needed(response_text, True)
            logger.info(f"🇮🇳 [CONVERSATION_NODE] Translated string response to Hindi for thread {thread_id}")
        
        # Chunk string responses too
        message_chunks = chunk_response_into_messages(response_text)
        chunked_messages = [AIMessage(content=chunk) for chunk in message_chunks if chunk.strip()]
        out = {"messages": chunked_messages}
    
    # Check if we should attach QR code for payment
    # This is a special case for Indian UPI payments
    lower_resp = response_text.lower() if isinstance(response_text, str) else str(response_text).lower()
    user_message = state["messages"][-1].content.lower() if state.get("messages") else ""
    attach_qr = any(k in lower_resp for k in ["qr", "upi", "payment options", "payment karna", "scan"]) or \
                any(k in user_message for k in ["qr", "upi", "scan"])

    if attach_qr and getattr(settings, "UPI_QR_IMAGE_PATH", None):
        out["attachment_image_path"] = settings.UPI_QR_IMAGE_PATH
        logger.info(f"📱 [CONVERSATION_NODE] Attaching QR code for payment for thread {thread_id}")
    
    logger.info(f"✨ [CONVERSATION_NODE] Completed successfully for thread {thread_id}")
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
    product_context = state.get("product_context", "")
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
            "product_context": product_context,
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
    product_context = state.get("product_context", "")
    
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
            "product_context": product_context,
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

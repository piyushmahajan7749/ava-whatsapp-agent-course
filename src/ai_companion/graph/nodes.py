"""Conversation and workflow nodes — Saarthi real-estate agent branch.

Flow per WhatsApp turn:
  memory_extraction → load_session_context → conversation ⇄ tools → (summarize)

load_session_context calls the Saarthi website's Agent API: it upserts the
lead, records the inbound message in the CRM transcript, and returns the live
lead context (requirements, matches already sent, open visit, earliest allowed
visit slot) which is injected into the system prompt.
"""

import asyncio
import logging

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from ai_companion.graph.state import AICompanionState
from ai_companion.graph.utils.chains import get_character_response_chain
from ai_companion.graph.utils.helpers import (
    chunk_response_into_messages,
    get_chat_model,
)
from ai_companion.modules.language.hindi_detection import contains_hindi, should_respond_in_hindi
from ai_companion.modules.language.hindi_translation import translate_response_if_needed
from ai_companion.modules.memory.long_term.memory_manager import get_memory_manager
from ai_companion.modules.saarthi.client import (
    SaarthiAPIError,
    format_lead_context,
    get_saarthi_client,
    phone_from_config,
)
from ai_companion.modules.saarthi.tools import get_saarthi_tools
from ai_companion.settings import settings

logger = logging.getLogger(__name__)


async def load_session_context_node(state: AICompanionState, config: RunnableConfig):
    """Load all session context upfront in a single pass.

    1. Lead CRM context from the Saarthi Agent API (also records the inbound
       message in the CRM transcript — the website is the source of truth).
    2. User-specific long-term memories (Qdrant).
    """
    thread_id = config.get("configurable", {}).get("thread_id") if config else None
    logger.info(f"📦 [SESSION_CONTEXT] Loading session context for thread {thread_id}")

    # --- inbound message + WhatsApp profile name (set by the webhook) ---
    inbound_text: str | None = None
    profile_name: str | None = None
    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        if isinstance(last, HumanMessage) and isinstance(last.content, str):
            inbound_text = last.content
            profile_name = (last.additional_kwargs or {}).get("wa_profile_name")

    # --- 1. Lead CRM context (Saarthi website Agent API) ---
    lead_context = ""
    phone = phone_from_config(config)
    client = get_saarthi_client()
    if client.configured and phone:
        try:
            ctx = await asyncio.to_thread(client.get_context, phone, profile_name, inbound_text)
            lead_context = format_lead_context(ctx)
            logger.info(
                f"🏠 [SESSION_CONTEXT] Lead context loaded: status={ctx.get('status')} "
                f"matches_sent={len(ctx.get('sentMatches') or [])}"
            )
        except SaarthiAPIError as exc:
            logger.error(f"❌ [SESSION_CONTEXT] Saarthi API context failed (continuing without): {exc}")
    elif not client.configured:
        logger.warning("⚠️ [SESSION_CONTEXT] Saarthi API not configured — set SAARTHI_API_URL/SAARTHI_API_KEY")

    # --- 2. Long-term memories (non-fatal: a Qdrant outage must not kill the turn) ---
    memory_context = ""
    try:
        recent_text = " ".join(
            m.content for m in messages[-3:] if hasattr(m, "content") and isinstance(m.content, str)
        )
        memory_manager = get_memory_manager()
        memories = memory_manager.get_relevant_memories(recent_text, user_id=thread_id) if recent_text else []
        memory_context = memory_manager.format_memories_for_prompt(memories)
        if memories:
            logger.info(f"🧠 [SESSION_CONTEXT] Memory loaded: {len(memories)} memories retrieved")
    except Exception as exc:
        logger.error(f"❌ [SESSION_CONTEXT] Memory retrieval failed (continuing without): {exc}")

    logger.info(f"✅ [SESSION_CONTEXT] Session context loaded for thread {thread_id}")
    return {"lead_context": lead_context, "memory_context": memory_context}


async def conversation_node(state: AICompanionState, config: RunnableConfig):
    """Unified conversational agent with tool calling.

    1. Uses preloaded session context (lead CRM + memories)
    2. Tools enabled — the LLM decides when to search/save/schedule
    3. Hindi mirroring + WhatsApp-style chunking on the way out
    """
    from ai_companion.core.prompts import UNIFIED_AGENT_INSTRUCTIONS

    thread_id = config.get("configurable", {}).get("thread_id") if config else "unknown"
    logger.info(
        f"🗣️ [CONVERSATION] Starting for thread {thread_id} | Messages: {len(state.get('messages', []))}"
    )

    memory_context = state.get("memory_context", "")
    lead_context = state.get("lead_context", "")

    # Detect Hindi for response mirroring
    user_messages = [msg for msg in state.get("messages", []) if hasattr(msg, "content") and msg.content]
    should_translate_to_hindi = should_respond_in_hindi(user_messages)

    chain = get_character_response_chain(
        summary=state.get("summary", ""),
        enable_tools=True,
        additional_context=UNIFIED_AGENT_INSTRUCTIONS,
    )

    logger.info(f"🤖 [CONVERSATION] Invoking LLM for thread {thread_id}")
    try:
        response = await chain.ainvoke(
            {
                "messages": state["messages"],
                "memory_context": memory_context,
                "lead_context": lead_context,
                "response_language": "hindi" if should_translate_to_hindi else "english",
            },
            config,
        )
        logger.info(f"✅ [CONVERSATION] Response received for thread {thread_id}")
    except Exception as e:
        logger.error(f"❌ [CONVERSATION] Error for thread {thread_id}: {e}", exc_info=True)
        raise

    # Tool calls: hand off to the tools node
    if isinstance(response, AIMessage) and response.tool_calls:
        tool_names = [tc.get("name") for tc in response.tool_calls]
        logger.info(f"🛠️ [CONVERSATION] Tool calls: {tool_names}")
        return {"messages": [response]}

    response_text = response.content if isinstance(response, AIMessage) else str(response)
    logger.info(f"💬 [CONVERSATION] Text response: {response_text[:100]}...")

    # Hindi fallback translation if the model answered in English for a Hindi user
    if should_translate_to_hindi and not contains_hindi(response_text):
        response_text = translate_response_if_needed(response_text, True)
        logger.info("🇮🇳 [CONVERSATION] Translated to Hindi (fallback)")

    # Chunk into WhatsApp-sized messages
    message_chunks = chunk_response_into_messages(response_text)
    chunked_messages = [AIMessage(content=chunk) for chunk in message_chunks if chunk.strip()]
    logger.info(f"📝 [CONVERSATION] Split into {len(chunked_messages)} messages")

    return {"messages": chunked_messages}


async def summarize_conversation_node(state: AICompanionState):
    model = get_chat_model()
    summary = state.get("summary", "")

    if summary:
        summary_message = (
            f"This is summary of the conversation to date between Saarthi (the property assistant) and the buyer: {summary}\n\n"
            "Extend the summary by taking into account the new messages above. Preserve all property "
            "requirements, properties discussed, and visit plans:"
        )
    else:
        summary_message = (
            "Create a summary of the conversation above between Saarthi (the property assistant) and the buyer. "
            "Capture their property requirements (buy/rent, type, BHK, budget, localities, timeline), "
            "properties shared and their reactions, and any visit plans:"
        )

    messages = state["messages"] + [HumanMessage(content=summary_message)]
    response = await model.ainvoke(messages)

    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][: -settings.TOTAL_MESSAGES_AFTER_SUMMARY]]
    return {"summary": response.content, "messages": delete_messages}


async def memory_extraction_node(state: AICompanionState, config: RunnableConfig):
    """Extract and store important information from the last message (Qdrant, per-user).

    Non-fatal: a memory-store outage must never block the lead conversation.
    """
    if not state["messages"]:
        return {}

    thread_id = config.get("configurable", {}).get("thread_id") if config else None
    try:
        memory_manager = get_memory_manager()
        await memory_manager.extract_and_store_memories(state["messages"][-1], user_id=thread_id)
        logger.debug(f"Memory extraction complete for user: {thread_id}")
    except Exception as exc:
        logger.error(f"❌ [MEMORY] Extraction failed (continuing without): {exc}")
    return {}


# Tool executor for the conversation ⇄ tools loop
tools_node = ToolNode(get_saarthi_tools())

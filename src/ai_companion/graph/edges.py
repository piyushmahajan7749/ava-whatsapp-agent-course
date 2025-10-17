from langgraph.graph import END
from typing_extensions import Literal
from langchain_core.messages import AIMessage
import logging

from ai_companion.graph.state import AICompanionState
from ai_companion.settings import settings


logger = logging.getLogger(__name__)


def should_summarize_conversation(
    state: AICompanionState,
) -> Literal["summarize_conversation_node", "__end__"]:
    """
    Decide if conversation should be summarized based on message count.
    
    Summarization helps manage context window by compressing old messages.
    """
    messages = state["messages"]
    message_count = len(messages)

    if message_count > settings.TOTAL_MESSAGES_SUMMARY_TRIGGER:
        logger.info(f"📝 [EDGE] Summarization triggered: {message_count} messages > {settings.TOTAL_MESSAGES_SUMMARY_TRIGGER} threshold")
        return "summarize_conversation_node"

    logger.debug(f"📝 [EDGE] No summarization needed: {message_count} messages")
    return END


def route_after_conversation(
    state: AICompanionState,
) -> Literal["tools_node", "should_summarize"]:
    """
    Route after conversation node based on whether tools were called.
    
    If the last message contains tool calls, route to tools_node for execution.
    Otherwise, proceed to summarization check and potentially end the conversation.
    
    This creates a tool execution loop:
    conversation_node → (has tools?) → tools_node → conversation_node → (no tools?) → end
    """
    messages = state["messages"]
    if not messages:
        logger.warning("⚠️ [EDGE] No messages in state, routing to summarization")
        return "should_summarize"
    
    last_message = messages[-1]
    
    # Check if the last message is an AIMessage with tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        tool_names = [tc.get('name', 'unknown') for tc in last_message.tool_calls]
        logger.info(f"🛠️ [EDGE] Routing to tools_node for execution: {tool_names}")
        return "tools_node"
    
    logger.debug("✅ [EDGE] No tools called, routing to summarization check")
    return "should_summarize"

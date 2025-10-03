from langgraph.graph import END
from typing_extensions import Literal
from langchain_core.messages import AIMessage

from ai_companion.graph.state import AICompanionState
from ai_companion.settings import settings


def should_summarize_conversation(
    state: AICompanionState,
) -> Literal["summarize_conversation_node", "__end__"]:
    messages = state["messages"]

    if len(messages) > settings.TOTAL_MESSAGES_SUMMARY_TRIGGER:
        return "summarize_conversation_node"

    return END


def select_workflow(
    state: AICompanionState,
) -> Literal["conversation_node", "image_node", "audio_node"]:
    workflow = state["workflow"]

    if workflow == "image":
        return "image_node"

    elif workflow == "audio":
        return "audio_node"

    else:
        return "conversation_node"


def route_after_conversation(
    state: AICompanionState,
) -> Literal["tools_node", "should_summarize"]:
    """
    Route after conversation node based on whether tools were called.
    
    If the last message contains tool calls, route to tools_node.
    Otherwise, proceed to summarization check.
    """
    messages = state["messages"]
    if not messages:
        return "should_summarize"
    
    last_message = messages[-1]
    
    # Check if the last message is an AIMessage with tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools_node"
    
    return "should_summarize"

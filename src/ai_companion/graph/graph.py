from functools import lru_cache

import logging

from langgraph.graph import END, START, StateGraph

from ai_companion.graph.edges import (
    route_after_conversation,
    should_summarize_conversation,
)
from ai_companion.graph.nodes import (
    conversation_node,
    load_session_context_node,
    memory_extraction_node,
    summarize_conversation_node,
    tools_node,
)
from ai_companion.graph.state import AICompanionState

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def create_workflow_graph():
    """Saarthi real-estate agent workflow.

    Flow:
    START
      ↓
    1. memory_extraction_node → Extract long-term memories from user message
      ↓
    2. load_session_context_node → Lead CRM context (Saarthi Agent API) + memories
      ↓
    3. conversation_node → Qualifier brain with real-estate tools
      ↓
    [has tool calls?]
      ↙        ↘
    tools_node   [check summarization]
      ↓              ↓
    conversation   [summarize or END]
    """
    logger.info("🏗️ [GRAPH] Creating Saarthi agent workflow...")

    graph_builder = StateGraph(AICompanionState)

    graph_builder.add_node("memory_extraction_node", memory_extraction_node)
    graph_builder.add_node("load_session_context_node", load_session_context_node)
    graph_builder.add_node("conversation_node", conversation_node)
    graph_builder.add_node("tools_node", tools_node)
    graph_builder.add_node("summarize_conversation_node", summarize_conversation_node)

    # Linear preprocessing flow
    graph_builder.add_edge(START, "memory_extraction_node")
    graph_builder.add_edge("memory_extraction_node", "load_session_context_node")
    graph_builder.add_edge("load_session_context_node", "conversation_node")

    # Tool execution loop: conversation ⇄ tools
    graph_builder.add_conditional_edges(
        "conversation_node",
        route_after_conversation,
        {
            "tools_node": "tools_node",
            "check_summarize": "check_summarize",
        },
    )
    graph_builder.add_edge("tools_node", "conversation_node")

    # Summarization check and end
    graph_builder.add_node("check_summarize", lambda state: {})
    graph_builder.add_conditional_edges("check_summarize", should_summarize_conversation)
    graph_builder.add_edge("summarize_conversation_node", END)

    logger.info("✅ [GRAPH] Saarthi agent workflow created")
    return graph_builder


# Compiled without a checkpointer. Used for LangGraph Studio
graph = create_workflow_graph().compile()

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
import logging

from ai_companion.graph.edges import (
    route_after_conversation,
    should_summarize_conversation,
)
from ai_companion.graph.nodes import (
    audio_node,
    context_injection_node,
    product_injection_node,
    intent_classification_node,
    payment_verification_node,
    conversation_node,
    image_node,
    memory_extraction_node,
    memory_injection_node,
    summarize_conversation_node,
    tools_node,
)
from ai_companion.graph.state import AICompanionState


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def create_workflow_graph():
    """
    Create simplified workflow graph with unified conversational agent.
    
    Flow:
    1. Memory extraction → Extract user preferences and info
    2. Context injection → Add schedule context
    3. Product injection → Add product/service context (pooja, products, packages, services)
    4. Payment verification → Check for payment screenshots
    5. Memory injection → Retrieve relevant memories
    6. Conversation node → Unified agent handles all interactions
    7. Tool execution (if needed) → Execute calendar/other tools
    8. Summarization (if needed) → Compress long conversations
    
    Removed:
    - Router node (intent is now inferred naturally by the LLM)
    - Workflow selection (no more audio/image/text branching)
    - Complex conditional logic (simplified to single conversation path)
    """
    logger.info("🏗️ [GRAPH] Creating simplified workflow graph...")
    
    graph_builder = StateGraph(AICompanionState)

    # Add nodes - simplified to single conversation path
    graph_builder.add_node("memory_extraction_node", memory_extraction_node)
    graph_builder.add_node("context_injection_node", context_injection_node)
    graph_builder.add_node("product_injection_node", product_injection_node)
    graph_builder.add_node("intent_classification_node", intent_classification_node)
    graph_builder.add_node("payment_verification_node", payment_verification_node)
    graph_builder.add_node("memory_injection_node", memory_injection_node)
    graph_builder.add_node("conversation_node", conversation_node)
    graph_builder.add_node("tools_node", tools_node)
    graph_builder.add_node("summarize_conversation_node", summarize_conversation_node)
    
    # Legacy nodes kept for compatibility (may be used by other interfaces)
    graph_builder.add_node("image_node", image_node)
    graph_builder.add_node("audio_node", audio_node)

    # Define simplified linear flow
    logger.debug("🔗 [GRAPH] Building node connections...")
    
    # 1. Extract memories from user message
    graph_builder.add_edge(START, "memory_extraction_node")

    # 2. Inject all contextual information (no routing needed)
    graph_builder.add_edge("memory_extraction_node", "context_injection_node")
    graph_builder.add_edge("context_injection_node", "product_injection_node")
    graph_builder.add_edge("product_injection_node", "intent_classification_node")
    graph_builder.add_edge("intent_classification_node", "payment_verification_node")
    graph_builder.add_edge("payment_verification_node", "memory_injection_node")

    # 3. Single conversation node handles everything
    graph_builder.add_edge("memory_injection_node", "conversation_node")

    # 4. After conversation, check if tools were called
    # If yes -> execute tools -> loop back to conversation_node
    # If no -> proceed to summarization check
    graph_builder.add_conditional_edges(
        "conversation_node",
        route_after_conversation,
        {
            "tools_node": "tools_node",
            "should_summarize": "should_summarize",
        }
    )
    
    # 5. After tools execute, loop back to conversation_node for LLM to respond with results
    graph_builder.add_edge("tools_node", "conversation_node")
    
    # 6. Summarization routing
    graph_builder.add_node("should_summarize", lambda state: {})
    graph_builder.add_conditional_edges("should_summarize", should_summarize_conversation)

    # 7. Legacy: Check for summarization after image and audio responses (if still used)
    graph_builder.add_conditional_edges("image_node", should_summarize_conversation)
    graph_builder.add_conditional_edges("audio_node", should_summarize_conversation)
    
    # 8. End flow after summarization
    graph_builder.add_edge("summarize_conversation_node", END)

    logger.info("✅ [GRAPH] Workflow graph created successfully")
    return graph_builder


# Compiled without a checkpointer. Used for LangGraph Studio
graph = create_workflow_graph().compile()

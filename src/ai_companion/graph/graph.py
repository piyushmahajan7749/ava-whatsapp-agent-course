from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from ai_companion.graph.edges import (
    route_after_conversation,
    select_workflow,
    should_summarize_conversation,
)
from ai_companion.graph.nodes import (
    audio_node,
    context_injection_node,
    pooja_injection_node,
    conversation_node,
    image_node,
    memory_extraction_node,
    memory_injection_node,
    router_node,
    summarize_conversation_node,
    tools_node,
)
from ai_companion.graph.state import AICompanionState


@lru_cache(maxsize=1)
def create_workflow_graph():
    graph_builder = StateGraph(AICompanionState)

    # Add all nodes
    graph_builder.add_node("memory_extraction_node", memory_extraction_node)
    graph_builder.add_node("router_node", router_node)
    graph_builder.add_node("context_injection_node", context_injection_node)
    graph_builder.add_node("pooja_injection_node", pooja_injection_node)
    graph_builder.add_node("memory_injection_node", memory_injection_node)
    graph_builder.add_node("conversation_node", conversation_node)
    graph_builder.add_node("image_node", image_node)
    graph_builder.add_node("audio_node", audio_node)
    graph_builder.add_node("tools_node", tools_node)  # New: Tool execution node
    graph_builder.add_node("summarize_conversation_node", summarize_conversation_node)

    # Define the flow
    # First extract memories from user message
    graph_builder.add_edge(START, "memory_extraction_node")

    # Then determine response type
    graph_builder.add_edge("memory_extraction_node", "router_node")

    # Then inject both context and memories
    graph_builder.add_edge("router_node", "context_injection_node")
    graph_builder.add_edge("context_injection_node", "pooja_injection_node")
    graph_builder.add_edge("pooja_injection_node", "memory_injection_node")

    # Then proceed to appropriate response node
    graph_builder.add_conditional_edges("memory_injection_node", select_workflow)

    # After conversation_node, check if tools were called
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
    
    # After tools execute, loop back to conversation_node to let LLM respond with results
    graph_builder.add_edge("tools_node", "conversation_node")
    
    # Create a separate "should_summarize" node for routing
    # (We use a lambda as a passthrough since we need a named target)
    graph_builder.add_node("should_summarize", lambda state: {})
    graph_builder.add_conditional_edges("should_summarize", should_summarize_conversation)

    # Check for summarization after image and audio responses
    graph_builder.add_conditional_edges("image_node", should_summarize_conversation)
    graph_builder.add_conditional_edges("audio_node", should_summarize_conversation)
    graph_builder.add_edge("summarize_conversation_node", END)

    return graph_builder


# Compiled without a checkpointer. Used for LangGraph Studio
graph = create_workflow_graph().compile()

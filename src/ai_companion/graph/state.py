from langgraph.graph import MessagesState


class AICompanionState(MessagesState):
    """State for the Saarthi real-estate WhatsApp agent.

    Extends MessagesState with session-loaded context. All context is loaded
    upfront in load_session_context_node.

    Attributes:
        summary (str): Rolling conversation summary for context management.
        attachment_image_path (str): Path of an image to attach to the reply
            (unused on this branch; kept for webhook interface compatibility).
        memory_context (str): User-specific long-term memories (Qdrant).
        lead_context (str): Live CRM context for this buyer from the Saarthi
            website Agent API — requirements, status, matches already sent,
            open visit, and the earliest allowed visit slot.
    """

    summary: str
    attachment_image_path: str
    memory_context: str
    lead_context: str

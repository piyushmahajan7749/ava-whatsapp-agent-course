"""
API endpoints for conversation data access.
Used by Next.js admin dashboard to query conversations from Qdrant.
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ai_companion.modules.memory.long_term.vector_store import get_vector_store, Memory

logger = logging.getLogger(__name__)

conversations_router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationSummary(BaseModel):
    """Summary of a conversation for list view."""
    user_id: str
    last_message: str
    timestamp: str
    message_count: int
    score: float


class ConversationMessage(BaseModel):
    """Individual message in a conversation."""
    text: str
    timestamp: str
    message_id: Optional[str] = None
    message_type: Optional[str] = None  # e.g., "user" or "assistant"


class ConversationDetail(BaseModel):
    """Detailed conversation with all messages."""
    user_id: str
    messages: List[ConversationMessage]
    total_messages: int


@conversations_router.get("/list", response_model=List[ConversationSummary])
async def list_conversations(
    limit: int = Query(50, ge=1, le=200, description="Number of conversations to return"),
    search: Optional[str] = Query(None, description="Search query for filtering conversations"),
):
    """
    Get list of recent conversations.
    
    Args:
        limit: Maximum number of conversations to return
        search: Optional search query to filter conversations
        
    Returns:
        List of conversation summaries
    """
    try:
        vector_store = get_vector_store()
        
        # Use search query if provided, otherwise get all memories
        query = search if search else "conversation messages"
        memories = vector_store.search_memories(query, k=limit)
        
        # Group by user_id and get most recent per user
        user_conversations = {}
        for memory in memories:
            user_id = memory.metadata.get("user_id", "unknown")
            timestamp = memory.metadata.get("timestamp", datetime.now().isoformat())
            
            if user_id not in user_conversations or timestamp > user_conversations[user_id]["timestamp"]:
                user_conversations[user_id] = {
                    "user_id": user_id,
                    "last_message": memory.text[:200] + "..." if len(memory.text) > 200 else memory.text,
                    "timestamp": timestamp,
                    "message_count": 1,  # This is approximate, would need better tracking
                    "score": memory.score or 0.0,
                }
        
        # Convert to list and sort by timestamp
        conversations = list(user_conversations.values())
        conversations.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return conversations[:limit]
        
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {str(e)}")


@conversations_router.get("/{user_id}", response_model=ConversationDetail)
async def get_conversation(
    user_id: str,
    limit: int = Query(100, ge=1, le=500, description="Number of messages to return"),
):
    """
    Get detailed conversation for a specific user.
    
    Args:
        user_id: User identifier (phone number)
        limit: Maximum number of messages to return
        
    Returns:
        Detailed conversation with all messages
    """
    try:
        vector_store = get_vector_store()
        
        # Get all memories for this user
        memories = vector_store.search_memories(
            query="conversation",  # Generic query to get all
            user_id=user_id,
            k=limit,
        )
        
        if not memories:
            raise HTTPException(status_code=404, detail=f"No conversation found for user {user_id}")
        
        # Convert memories to messages
        messages = []
        for memory in memories:
            messages.append(ConversationMessage(
                text=memory.text,
                timestamp=memory.metadata.get("timestamp", datetime.now().isoformat()),
                message_id=memory.metadata.get("id"),
                message_type=memory.metadata.get("type", "unknown"),
            ))
        
        # Sort by timestamp (oldest first)
        messages.sort(key=lambda x: x.timestamp)
        
        return ConversationDetail(
            user_id=user_id,
            messages=messages,
            total_messages=len(messages),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversation: {str(e)}")


@conversations_router.get("/search", response_model=List[ConversationSummary])
async def search_conversations(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
):
    """
    Search conversations by semantic similarity.
    
    Args:
        q: Search query string
        limit: Maximum number of results to return
        
    Returns:
        List of matching conversation summaries
    """
    try:
        vector_store = get_vector_store()
        
        # Semantic search across all conversations
        memories = vector_store.search_memories(q, k=limit)
        
        # Group by user and return summaries
        user_results = {}
        for memory in memories:
            user_id = memory.metadata.get("user_id", "unknown")
            
            if user_id not in user_results:
                user_results[user_id] = {
                    "user_id": user_id,
                    "last_message": memory.text[:200] + "..." if len(memory.text) > 200 else memory.text,
                    "timestamp": memory.metadata.get("timestamp", datetime.now().isoformat()),
                    "message_count": 1,
                    "score": memory.score or 0.0,
                }
        
        # Convert to list and sort by relevance score
        results = list(user_results.values())
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results
        
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@conversations_router.get("/stats", response_model=dict)
async def get_conversation_stats():
    """
    Get overall conversation statistics.
    
    Returns:
        Dictionary with stats like total conversations, total messages, etc.
    """
    try:
        vector_store = get_vector_store()
        
        # Get sample of memories to calculate stats
        memories = vector_store.search_memories("conversation", k=1000)
        
        # Count unique users
        unique_users = set()
        for memory in memories:
            user_id = memory.metadata.get("user_id")
            if user_id:
                unique_users.add(user_id)
        
        return {
            "total_conversations": len(unique_users),
            "total_messages": len(memories),
            "average_messages_per_user": len(memories) / len(unique_users) if unique_users else 0,
        }
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


"""
API endpoints for conversation data access.
Used by Next.js admin dashboard to query conversations from short-term memory (SQLite).
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Import short-term memory reader for actual chat messages
from ai_companion.modules.memory.short_term_reader import ShortTermMemoryReader
from ai_companion.settings import settings

logger = logging.getLogger(__name__)

# Initialize short-term memory reader
memory_reader = None
try:
    import os
    db_path = settings.SHORT_TERM_MEMORY_DB_PATH
    
    # Check if database file exists
    if not os.path.exists(db_path):
        logger.warning(f"⚠️  Database file does not exist: {db_path}")
        logger.info("Trying alternative path: short_term_memory/memory.db")
        alt_path = "short_term_memory/memory.db"
        if os.path.exists(alt_path):
            db_path = alt_path
            logger.info(f"✓ Using alternative path: {alt_path}")
        else:
            logger.error(f"✗ Alternative path also doesn't exist: {alt_path}")
            raise FileNotFoundError(f"Database not found at {settings.SHORT_TERM_MEMORY_DB_PATH} or {alt_path}")
    
    memory_reader = ShortTermMemoryReader(db_path)
    logger.info(f"✓ Short-term memory reader initialized successfully (DB: {db_path})")
    
    # Test that it actually works
    test_threads = memory_reader.get_all_thread_ids(limit=1)
    logger.info(f"✓ Test query successful, found {len(test_threads)} threads in database")
    
except Exception as e:
    logger.error(f"✗ CRITICAL: Failed to initialize memory reader: {e}")
    logger.exception("Full traceback:")
    memory_reader = None
    logger.warning("⚠️  API will return mock data instead of real conversations!")

# Create router without prefix first to test - matches WhatsApp pattern
conversations_router = APIRouter(tags=["conversations"])

# Simple test endpoint to verify router is working
@conversations_router.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify the router is working."""
    return {"message": "Conversations router is working!", "status": "ok"}


@conversations_router.get("/debug_memory")
async def debug_memory():
    """Debug endpoint to check memory reader status."""
    if not memory_reader:
        return {
            "status": "error",
            "message": "Memory reader not initialized",
            "memory_reader": None
        }
    
    try:
        # Get sample thread IDs
        thread_ids = memory_reader.get_all_thread_ids(limit=5)
        
        return {
            "status": "success",
            "memory_reader_connected": True,
            "db_path": settings.SHORT_TERM_MEMORY_DB_PATH,
            "sample_thread_ids": thread_ids,
            "total_threads_sampled": len(thread_ids)
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


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


@conversations_router.get("/conversations_list", response_model=List[ConversationSummary])
async def list_conversations(
    limit: int = Query(50, ge=1, le=200, description="Number of conversations to return"),
    search: Optional[str] = Query(default=None, description="Search query for filtering conversations"),
):
    """
    Get list of recent conversations from short-term memory (actual chat history).
    
    Args:
        limit: Maximum number of conversations to return
        search: Optional search query to filter conversations
        
    Returns:
        List of conversation summaries with real chat messages
    """
    try:
        if not memory_reader:
            logger.warning("Memory reader not available, returning mock data")
            # Fallback to mock data if memory reader is not available
            mock_conversations = [
                ConversationSummary(
                    user_id="test_user_1",
                    last_message="Hello, this is a test message from user 1",
                    timestamp=datetime.now().isoformat(),
                    message_count=5,
                    score=0.95
                ),
                ConversationSummary(
                    user_id="test_user_2", 
                    last_message="Another test message from user 2",
                    timestamp=datetime.now().isoformat(),
                    message_count=3,
                    score=0.88
                )
            ]
            
            # Apply search filter if provided
            if search and isinstance(search, str):
                mock_conversations = [conv for conv in mock_conversations 
                                    if search.lower() in conv.last_message.lower()]
            
            return mock_conversations[:limit]
        
        # Use real short-term memory data (actual chat messages)
        summaries = await memory_reader.get_conversation_summaries(limit=limit)
        
        # Apply search filter if provided
        if search and isinstance(search, str):
            summaries = [s for s in summaries if search.lower() in s["last_message"].lower()]
        
        # Convert to ConversationSummary objects
        conversations = []
        for summary in summaries:
            conversations.append(ConversationSummary(
                user_id=summary["user_id"],
                last_message=summary["last_message"],
                timestamp=summary["timestamp"],
                message_count=summary.get("message_count", 0),
                score=summary.get("score", 1.0)
            ))
        
        return conversations
        
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversations: {str(e)}")


@conversations_router.get("/conversation/{user_id}", response_model=ConversationDetail)
async def get_conversation(
    user_id: str,
    limit: int = Query(100, ge=1, le=500, description="Number of messages to return"),
):
    """
    Get detailed conversation for a specific user from short-term memory (actual chat history).
    
    Args:
        user_id: User identifier (phone number or UUID)
        limit: Maximum number of messages to return
        
    Returns:
        Detailed conversation with all actual chat messages
    """
    try:
        if not memory_reader:
            logger.warning("Memory reader not available, returning mock data")
            # Fallback to mock data if memory reader is not available
            mock_messages = [
                ConversationMessage(
                    text="Hello, how can I help you?",
                    timestamp=datetime.now().isoformat(),
                    message_id="msg_1",
                    message_type="assistant"
                ),
                ConversationMessage(
                    text="I need help with my booking",
                    timestamp=datetime.now().isoformat(),
                    message_id="msg_2", 
                    message_type="user"
                ),
                ConversationMessage(
                    text="I'd be happy to help with your booking. What do you need?",
                    timestamp=datetime.now().isoformat(),
                    message_id="msg_3",
                    message_type="assistant"
                )
            ]
            
            return ConversationDetail(
                user_id=user_id,
                messages=mock_messages,
                total_messages=len(mock_messages),
            )
        
        # Use real short-term memory data (actual chat messages)
        chat_messages = await memory_reader.get_messages_for_thread(user_id, limit=limit)
        
        # Convert to ConversationMessage objects
        messages = []
        for msg in chat_messages:
            messages.append(ConversationMessage(
                text=msg["text"],
                timestamp=msg.get("timestamp", datetime.now().isoformat()),
                message_id=msg.get("message_id"),
                message_type=msg.get("message_type", "unknown")
            ))
        
        return ConversationDetail(
            user_id=user_id,
            messages=messages,
            total_messages=len(messages),
        )
        
    except Exception as e:
        logger.error(f"Error fetching conversation for {user_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch conversation: {str(e)}")


@conversations_router.get("/conversations_search", response_model=List[ConversationSummary])
async def search_conversations(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
):
    """
    Search conversations by text matching in chat messages.
    
    Args:
        q: Search query string
        limit: Maximum number of results to return
        
    Returns:
        List of matching conversation summaries
    """
    try:
        if not memory_reader:
            logger.warning("Memory reader not available, returning mock data")
            # Fallback to mock data if memory reader is not available
            mock_results = [
                ConversationSummary(
                    user_id="search_user_1",
                    last_message=f"Found conversation matching '{q}'",
                    timestamp=datetime.now().isoformat(),
                    message_count=2,
                    score=0.92
                )
            ]
            
            return mock_results[:limit]
        
        # Get all conversations and filter by search query
        summaries = await memory_reader.get_conversation_summaries(limit=limit * 2)
        
        # Filter by search query (simple text matching)
        matching_summaries = [
            s for s in summaries 
            if q.lower() in s["last_message"].lower()
        ]
        
        # Convert to ConversationSummary objects
        conversations = []
        for summary in matching_summaries[:limit]:
            conversations.append(ConversationSummary(
                user_id=summary["user_id"],
                last_message=summary["last_message"],
                timestamp=summary["timestamp"],
                message_count=summary.get("message_count", 0),
                score=summary.get("score", 1.0)
            ))
        
        return conversations
        
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@conversations_router.get("/conversations_stats", response_model=dict)
async def get_conversation_stats():
    """
    Get overall conversation statistics from short-term memory.
    
    Returns:
        Dictionary with stats like total conversations, total messages, etc.
    """
    try:
        if not memory_reader:
            logger.warning("Memory reader not available, returning mock data")
            # Fallback to mock data if memory reader is not available
            return {
                "total_conversations": 25,
                "total_messages": 150,
                "average_messages_per_user": 6.0,
                "status": "mock_data"
            }
        
        # Use real short-term memory stats
        stats = await memory_reader.get_conversation_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


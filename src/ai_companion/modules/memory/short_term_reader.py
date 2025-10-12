"""
Module to read chat messages from the short-term memory SQLite database.
This provides access to actual chat history for the conversation API.
"""
import logging
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
import asyncio

logger = logging.getLogger(__name__)


class ShortTermMemoryReader:
    """Reader for accessing chat messages from SQLite short-term memory."""
    
    def __init__(self, db_path: str):
        """
        Initialize the reader.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        
    def get_all_thread_ids(self, limit: int = 100) -> List[str]:
        """
        Get all unique thread IDs (user identifiers).
        
        Args:
            limit: Maximum number of thread IDs to return
            
        Returns:
            List of thread IDs (phone numbers or UUIDs)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get unique thread IDs, ordered by most recent checkpoint
            cursor.execute("""
                SELECT DISTINCT thread_id 
                FROM checkpoints 
                ORDER BY checkpoint_id DESC 
                LIMIT ?
            """, (limit,))
            
            thread_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            return thread_ids
            
        except Exception as e:
            logger.error(f"Error getting thread IDs: {e}")
            return []
    
    async def get_messages_for_thread(self, thread_id: str, limit: int = 100) -> List[Dict]:
        """
        Get chat messages for a specific thread.
        
        Args:
            thread_id: User identifier (phone number or UUID)
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries with text, timestamp, and message_type
        """
        try:
            # Use AsyncSqliteSaver to properly deserialize checkpoints
            async with AsyncSqliteSaver.from_conn_string(self.db_path) as memory:
                # Get the latest checkpoint for this thread
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint_tuple = await memory.aget_tuple(config)
                
                if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
                    logger.warning(f"No checkpoint found for thread {thread_id}")
                    return []
                
                # The checkpoint contains the full state in channel_values
                checkpoint = checkpoint_tuple.checkpoint
                channel_values = checkpoint.get("channel_values", {})
                
                if not channel_values:
                    logger.warning(f"No channel values for thread {thread_id}")
                    return []
                
                messages = channel_values.get("messages", [])
                
                # Convert LangChain messages to simple dicts
                chat_messages = []
                for msg in messages[-limit:]:  # Get last N messages
                    if isinstance(msg, BaseMessage):
                        chat_messages.append({
                            "text": msg.content,
                            "timestamp": msg.additional_kwargs.get("timestamp", datetime.now().isoformat()),
                            "message_type": "user" if isinstance(msg, HumanMessage) else "assistant",
                            "message_id": msg.id if hasattr(msg, 'id') else None
                        })
                
                return chat_messages
                
        except Exception as e:
            logger.error(f"Error getting messages for thread {thread_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def get_conversation_summaries(self, limit: int = 50) -> List[Dict]:
        """
        Get conversation summaries for all threads.
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversation summary dictionaries
        """
        try:
            thread_ids = self.get_all_thread_ids(limit=limit)
            summaries = []
            
            for thread_id in thread_ids:
                # Get all messages to count them properly
                all_messages = await self.get_messages_for_thread(thread_id, limit=10000)
                
                if all_messages:
                    last_message = all_messages[-1]
                    summaries.append({
                        "user_id": thread_id,
                        "last_message": last_message["text"][:200],  # Truncate long messages
                        "timestamp": last_message.get("timestamp", datetime.now().isoformat()),
                        "message_count": len(all_messages),  # Accurate count
                        "score": 1.0
                    })
            
            # Sort by timestamp (newest first)
            summaries.sort(key=lambda s: s["timestamp"], reverse=True)
            
            return summaries
            
        except Exception as e:
            logger.error(f"Error getting conversation summaries: {e}")
            return []
    
    async def get_conversation_stats(self) -> Dict:
        """
        Get overall conversation statistics.
        
        Returns:
            Dictionary with conversation statistics
        """
        try:
            thread_ids = self.get_all_thread_ids(limit=10000)
            total_conversations = len(thread_ids)
            
            # For a sample of threads, count messages
            sample_size = min(50, total_conversations)
            total_messages = 0
            
            for thread_id in thread_ids[:sample_size]:
                messages = await self.get_messages_for_thread(thread_id, limit=10000)
                total_messages += len(messages)
            
            # Estimate total messages
            if sample_size > 0:
                avg_messages = total_messages / sample_size
                estimated_total = int(avg_messages * total_conversations)
            else:
                avg_messages = 0
                estimated_total = 0
            
            return {
                "total_conversations": total_conversations,
                "total_messages": estimated_total,
                "average_messages_per_user": round(avg_messages, 2),
                "status": "real_data"
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            return {
                "total_conversations": 0,
                "total_messages": 0,
                "average_messages_per_user": 0.0,
                "status": "error"
            }


async def get_short_term_memory_reader(db_path: str) -> ShortTermMemoryReader:
    """Factory function to create a ShortTermMemoryReader instance."""
    return ShortTermMemoryReader(db_path)


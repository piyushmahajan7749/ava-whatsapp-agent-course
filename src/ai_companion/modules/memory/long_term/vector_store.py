import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import List, Optional

from ai_companion.settings import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer


@dataclass
class Memory:
    """Represents a memory entry in the vector store."""

    text: str
    metadata: dict
    score: Optional[float] = None

    @property
    def id(self) -> Optional[str]:
        return self.metadata.get("id")

    @property
    def timestamp(self) -> Optional[datetime]:
        ts = self.metadata.get("timestamp")
        return datetime.fromisoformat(ts) if ts else None


class VectorStore:
    """A class to handle vector storage operations using Qdrant."""

    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    COLLECTION_NAME = "long_term_memory"
    SIMILARITY_THRESHOLD = 0.9  # Threshold for considering memories as similar

    _instance: Optional["VectorStore"] = None
    _initialized: bool = False

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._initialized:
            self._validate_env_vars()
            self.model = SentenceTransformer(self.EMBEDDING_MODEL)
            self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
            self._initialized = True

    def _validate_env_vars(self) -> None:
        """Validate that all required environment variables are set."""
        # Check settings directly instead of os.getenv
        # since settings loads from .env file via pydantic
        missing_vars = []
        if not settings.QDRANT_URL:
            missing_vars.append("QDRANT_URL")
        if not settings.QDRANT_API_KEY:
            missing_vars.append("QDRANT_API_KEY")
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _collection_exists(self) -> bool:
        """Check if the memory collection exists."""
        collections = self.client.get_collections().collections
        return any(col.name == self.COLLECTION_NAME for col in collections)

    def _create_collection(self) -> None:
        """Create a new collection for storing memories with user_id index."""
        from qdrant_client.models import PayloadSchemaType
        
        sample_embedding = self.model.encode("sample text")
        self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=len(sample_embedding),
                distance=Distance.COSINE,
            ),
        )
        
        # Create index for user_id filtering (required for user-specific memories)
        self.client.create_payload_index(
            collection_name=self.COLLECTION_NAME,
            field_name="user_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )

    def find_similar_memory(self, text: str, user_id: str = None) -> Optional[Memory]:
        """Find if a similar memory already exists.

        Args:
            text: The text to search for
            user_id: Optional user identifier to filter memories by user

        Returns:
            Optional Memory if a similar one is found
        """
        results = self.search_memories(text, user_id=user_id, k=1)
        if results and results[0].score >= self.SIMILARITY_THRESHOLD:
            return results[0]
        return None

    def store_memory(self, text: str, metadata: dict, user_id: str = None) -> None:
        """Store a new memory in the vector store or update if similar exists.

        Args:
            text: The text content of the memory
            metadata: Additional information about the memory (timestamp, type, etc.)
            user_id: Optional user identifier (phone number) to isolate memories per user
        """
        if not self._collection_exists():
            self._create_collection()

        # Add user_id to metadata if provided
        if user_id:
            metadata["user_id"] = user_id

        # Check if similar memory exists (for same user if user_id provided)
        similar_memory = self.find_similar_memory(text, user_id=user_id)
        if similar_memory and similar_memory.id:
            metadata["id"] = similar_memory.id  # Keep same ID for update

        embedding = self.model.encode(text)
        point = PointStruct(
            id=metadata.get("id", hash(text)),
            vector=embedding.tolist(),
            payload={
                "text": text,
                **metadata,
            },
        )

        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[point],
        )

    def search_memories(self, query: str, user_id: str = None, k: int = 5) -> List[Memory]:
        """Search for similar memories in the vector store.

        Args:
            query: Text to search for
            user_id: Optional user identifier to filter memories by user (phone number)
            k: Number of results to return

        Returns:
            List of Memory objects filtered by user if user_id provided
        """
        if not self._collection_exists():
            return []

        query_embedding = self.model.encode(query)
        
        # Build query filter if user_id is provided
        query_filter = None
        if user_id:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            query_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            )

        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_embedding.tolist(),
            query_filter=query_filter,
            limit=k,
        )

        return [
            Memory(
                text=hit.payload["text"],
                metadata={k: v for k, v in hit.payload.items() if k != "text"},
                score=hit.score,
            )
            for hit in results
        ]

    def get_conversation_messages(self, user_id: str, limit: int = 100) -> List[Memory]:
        """Get all messages for a specific user conversation.
        
        Args:
            user_id: User identifier (phone number)
            limit: Maximum number of messages to return
            
        Returns:
            List of Memory objects representing conversation messages
        """
        if not self._collection_exists():
            return []
            
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        # Filter by user_id and order by timestamp
        query_filter = Filter(
            must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        )
        
        # Get all points for this user
        results = self.client.scroll(
            collection_name=self.COLLECTION_NAME,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        # Convert to Memory objects and sort by timestamp
        memories = []
        for point in results[0]:  # results is a tuple (points, next_page_offset)
            memory = Memory(
                text=point.payload["text"],
                metadata={k: v for k, v in point.payload.items() if k != "text"},
                score=None
            )
            memories.append(memory)
        
        # Sort by timestamp (newest first)
        memories.sort(key=lambda m: m.timestamp or datetime.min, reverse=True)
        return memories

    def get_conversation_summaries(self, limit: int = 50, search: str = None) -> List[dict]:
        """Get conversation summaries for all users.
        
        Args:
            limit: Maximum number of conversations to return
            search: Optional search query to filter conversations
            
        Returns:
            List of conversation summary dictionaries
        """
        if not self._collection_exists():
            return []
            
        # Get all unique user_ids
        results = self.client.scroll(
            collection_name=self.COLLECTION_NAME,
            limit=10000,  # Get a large number to find all users
            with_payload=True,
            with_vectors=False
        )
        
        # Group by user_id
        user_conversations = {}
        for point in results[0]:
            user_id = point.payload.get("user_id")
            if not user_id:
                continue
                
            if user_id not in user_conversations:
                user_conversations[user_id] = []
            
            user_conversations[user_id].append({
                "text": point.payload["text"],
                "timestamp": point.payload.get("timestamp"),
                "message_type": point.payload.get("message_type", "unknown")
            })
        
        # Create summaries
        summaries = []
        for user_id, messages in user_conversations.items():
            if not messages:
                continue
                
            # Sort by timestamp to get latest message
            messages.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
            latest_message = messages[0]
            
            # Apply search filter if provided
            if search and search.lower() not in latest_message["text"].lower():
                continue
            
            summary = {
                "user_id": user_id,
                "last_message": latest_message["text"],
                "timestamp": latest_message.get("timestamp", datetime.now().isoformat()),
                "message_count": len(messages),
                "score": 1.0  # Default score for now
            }
            summaries.append(summary)
        
        # Sort by timestamp (newest first) and limit results
        summaries.sort(key=lambda s: s["timestamp"], reverse=True)
        return summaries[:limit]

    def search_conversations(self, query: str, limit: int = 20) -> List[dict]:
        """Search conversations by semantic similarity.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of conversation summary dictionaries matching the query
        """
        if not self._collection_exists():
            return []
            
        # Use semantic search to find relevant memories
        memories = self.search_memories(query, k=limit * 2)  # Get more to account for grouping
        
        # Group by user_id and create summaries
        user_conversations = {}
        for memory in memories:
            user_id = memory.metadata.get("user_id")
            if not user_id:
                continue
                
            if user_id not in user_conversations:
                user_conversations[user_id] = {
                    "messages": [],
                    "max_score": 0
                }
            
            user_conversations[user_id]["messages"].append(memory)
            user_conversations[user_id]["max_score"] = max(
                user_conversations[user_id]["max_score"], 
                memory.score or 0
            )
        
        # Create summaries
        summaries = []
        for user_id, data in user_conversations.items():
            messages = data["messages"]
            if not messages:
                continue
                
            # Get the most recent message
            latest_message = max(messages, key=lambda m: m.timestamp or datetime.min)
            
            summary = {
                "user_id": user_id,
                "last_message": latest_message.text,
                "timestamp": latest_message.timestamp.isoformat() if latest_message.timestamp else datetime.now().isoformat(),
                "message_count": len(messages),
                "score": data["max_score"]
            }
            summaries.append(summary)
        
        # Sort by score (highest first) and limit results
        summaries.sort(key=lambda s: s["score"], reverse=True)
        return summaries[:limit]

    def get_conversation_stats(self) -> dict:
        """Get overall conversation statistics.
        
        Returns:
            Dictionary with conversation statistics
        """
        if not self._collection_exists():
            return {
                "total_conversations": 0,
                "total_messages": 0,
                "average_messages_per_user": 0.0,
                "status": "no_data"
            }
            
        # Get all points to calculate stats
        results = self.client.scroll(
            collection_name=self.COLLECTION_NAME,
            limit=10000,  # Get a large number
            with_payload=True,
            with_vectors=False
        )
        
        # Group by user_id
        user_conversations = {}
        for point in results[0]:
            user_id = point.payload.get("user_id")
            if not user_id:
                continue
                
            if user_id not in user_conversations:
                user_conversations[user_id] = 0
            user_conversations[user_id] += 1
        
        total_conversations = len(user_conversations)
        total_messages = sum(user_conversations.values())
        average_messages = total_messages / total_conversations if total_conversations > 0 else 0
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "average_messages_per_user": round(average_messages, 2),
            "status": "real_data"
        }


@lru_cache
def get_vector_store() -> VectorStore:
    """Get or create the VectorStore singleton instance."""
    return VectorStore()

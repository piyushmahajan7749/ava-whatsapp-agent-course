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


@lru_cache
def get_vector_store() -> VectorStore:
    """Get or create the VectorStore singleton instance."""
    return VectorStore()

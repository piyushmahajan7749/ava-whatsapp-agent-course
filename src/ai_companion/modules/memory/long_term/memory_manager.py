import logging
import uuid
from datetime import datetime
from typing import List, Optional

from langchain_openai import AzureChatOpenAI

from ai_companion.core.prompts import MEMORY_ANALYSIS_PROMPT
from ai_companion.modules.memory.long_term.vector_store import get_vector_store
from ai_companion.settings import settings
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field


class MemoryAnalysis(BaseModel):
    """Result of analyzing a message for memory-worthy content."""

    is_important: bool = Field(
        ...,
        description="Whether the message is important enough to be stored as a memory",
    )
    formatted_memory: Optional[str] = Field(..., description="The formatted memory to be stored")


class MemoryManager:
    """Manager class for handling long-term memory operations."""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.logger = logging.getLogger(__name__)
        self.llm =  AzureChatOpenAI(
            azure_deployment=settings.SMALL_TEXT_MODEL_NAME,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            max_tokens=None,
            timeout=60.0,  # 60 second timeout to prevent hanging
            max_retries=3,  # Increased retries for flaky connections
            temperature=1,
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
        ).with_structured_output(MemoryAnalysis)

    async def _analyze_memory(self, message: str) -> MemoryAnalysis:
        """Analyze a message to determine importance and format if needed."""
        prompt = MEMORY_ANALYSIS_PROMPT.format(message=message)
        return await self.llm.ainvoke(prompt)

    async def extract_and_store_memories(self, message: BaseMessage, user_id: str = None) -> None:
        """Extract important information from a message and store in vector store.
        
        Args:
            message: The message to analyze
            user_id: Optional user identifier (phone number) to isolate memories per user
        """
        if message.type != "human":
            return

        # Analyze the message for importance and formatting
        analysis = await self._analyze_memory(message.content)
        if analysis.is_important and analysis.formatted_memory:
            # Check if similar memory exists (for same user if user_id provided)
            similar = self.vector_store.find_similar_memory(analysis.formatted_memory, user_id=user_id)
            if similar:
                # Skip storage if we already have a similar memory
                self.logger.info(f"Similar memory already exists for user {user_id}: '{analysis.formatted_memory}'")
                return

            # Store new memory with user context
            self.logger.info(f"Storing new memory for user {user_id}: '{analysis.formatted_memory}'")
            self.vector_store.store_memory(
                text=analysis.formatted_memory,
                metadata={
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                },
                user_id=user_id,
            )

    def get_relevant_memories(self, context: str, user_id: str = None) -> List[str]:
        """Retrieve relevant memories based on the current context.
        
        Args:
            context: The context to search for
            user_id: Optional user identifier to filter memories by user (phone number)
            
        Returns:
            List of memory texts relevant to the context and user
        """
        memories = self.vector_store.search_memories(context, user_id=user_id, k=settings.MEMORY_TOP_K)
        if memories:
            for memory in memories:
                self.logger.debug(f"Memory for user {user_id}: '{memory.text}' (score: {memory.score:.2f})")
        return [memory.text for memory in memories]

    def format_memories_for_prompt(self, memories: List[str]) -> str:
        """Format retrieved memories as bullet points."""
        if not memories:
            return ""
        return "\n".join(f"- {memory}" for memory in memories)


def get_memory_manager() -> MemoryManager:
    """Get a MemoryManager instance."""
    return MemoryManager()

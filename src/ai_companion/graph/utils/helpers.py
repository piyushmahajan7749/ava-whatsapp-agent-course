import re

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import AzureChatOpenAI


from ai_companion.modules.image.image_to_text import ImageToText
from ai_companion.modules.image.text_to_image import TextToImage
from ai_companion.modules.speech import TextToSpeech
from ai_companion.settings import settings


def get_chat_model(temperature: float = 1):
    return AzureChatOpenAI(
        azure_deployment=settings.TEXT_MODEL_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        max_tokens=300,  # Allow complete thoughts while keeping messages concise
        timeout=60.0,  # 60 second timeout to prevent hanging
        max_retries=3,  # Increased retries for flaky connections
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
    )


def get_text_to_speech_module():
    return TextToSpeech()


def get_text_to_image_module():
    return TextToImage()


def get_image_to_text_module():
    return ImageToText()


def remove_asterisk_content(text: str) -> str:
    """Remove content between asterisks from the text."""
    return re.sub(r"\*.*?\*", "", text).strip()


def chunk_message_by_sentences(text: str, max_length: int = 600) -> list[str]:
    """
    Split a message into chunks at sentence boundaries to avoid mid-sentence cutoffs.
    
    Args:
        text: The text to chunk
        max_length: Maximum character length per chunk (default: 600 chars)
    
    Returns:
        List of message chunks, each ending at a sentence boundary
    """
    if len(text) <= max_length:
        return [text]
    
    # Split on sentence boundaries (., !, ?, or newlines)
    # Keep the delimiter with the sentence
    sentences = re.split(r'([.!?\n])', text)
    
    # Rejoin sentences with their delimiters
    combined_sentences = []
    for i in range(0, len(sentences) - 1, 2):
        sentence = sentences[i]
        delimiter = sentences[i + 1] if i + 1 < len(sentences) else ""
        combined_sentences.append(sentence + delimiter)
    
    # If there's a remaining sentence without delimiter
    if len(sentences) % 2 == 1:
        combined_sentences.append(sentences[-1])
    
    # Group sentences into chunks under max_length
    chunks = []
    current_chunk = ""
    
    for sentence in combined_sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # If adding this sentence would exceed max_length
        if current_chunk and len(current_chunk) + len(sentence) + 1 > max_length:
            # Save current chunk and start a new one
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            # Add sentence to current chunk
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [text]


class AsteriskRemovalParser(StrOutputParser):
    def parse(self, text):
        return remove_asterisk_content(super().parse(text))


def get_small_chat_model(temperature: float = 0):
    """Return the small Azure OpenAI chat model (gpt-5-mini)."""
    return AzureChatOpenAI(
        azure_deployment=settings.SMALL_TEXT_MODEL_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        max_tokens=None,
        timeout=60.0,  # 60 second timeout to prevent hanging
        max_retries=3,  # Increased retries for flaky connections
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
        temperature=temperature,
    )

import re

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import AzureChatOpenAI


from ai_companion.modules.image.image_to_text import ImageToText
from ai_companion.modules.speech import TextToSpeech
from ai_companion.settings import settings


def get_chat_model(temperature: float = 1, max_tokens: int = 450):
    """
    Get chat model with parameters optimized for short, focused messages.

    Args:
        temperature: Accepted for call-site compatibility but NOT forwarded —
            the gpt-5 deployment only supports the default temperature (1).
        max_tokens: Output cap. gpt-5 deployments reject `max_tokens`, so we send
            it as `max_completion_tokens` via model_kwargs.
    """
    _ = temperature  # gpt-5-chat: only temperature=1 is supported (langchain
    # otherwise sends its 0.7 default, which the model rejects)
    return AzureChatOpenAI(
        azure_deployment=settings.TEXT_MODEL_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        temperature=1,
        timeout=60.0,  # 60 second timeout to prevent hanging
        max_retries=3,  # Increased retries for flaky connections
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
        model_kwargs={"max_completion_tokens": max_tokens},  # gpt-5 family
    )


def get_text_to_speech_module():
    return TextToSpeech()


def chunk_response_into_messages(response_text: str) -> list:
    """
    Split a long response into multiple focused messages.
    
    Args:
        response_text: The full response text from the LLM
        
    Returns:
        List of message chunks, each focused on one topic/question
    """
    if not response_text or len(response_text.strip()) < 50:
        return [response_text.strip()]
    
    # Split by common sentence boundaries
    sentences = []
    current_sentence = ""
    
    for char in response_text:
        current_sentence += char
        if char in '.!?':
            sentences.append(current_sentence.strip())
            current_sentence = ""
    
    if current_sentence.strip():
        sentences.append(current_sentence.strip())
    
    # Group sentences into focused messages
    messages = []
    current_message = ""
    
    for sentence in sentences:
        if not sentence:
            continue
            
        # If adding this sentence would make the message too long, start a new one
        if len(current_message + " " + sentence) > 200:
            if current_message:
                messages.append(current_message.strip())
            current_message = sentence
        else:
            if current_message:
                current_message += " " + sentence
            else:
                current_message = sentence
    
    if current_message.strip():
        messages.append(current_message.strip())
    
    # Ensure we have at least one message
    if not messages:
        messages = [response_text.strip()]
    
    return messages


def get_image_to_text_module():
    return ImageToText()


def remove_asterisk_content(text: str) -> str:
    """Remove content between asterisks from the text."""
    return re.sub(r"\*.*?\*", "", text).strip()


def strip_markdown_formatting(text: str) -> str:
    """Strip WhatsApp/markdown emphasis markers (*, _, ~, `, headings, bullets)
    while KEEPING the words. So "*monthly budget*" -> "monthly budget".

    The bot must read as a plain human texting — no bold/italic/code formatting.
    """
    if not text:
        return text
    # Paired emphasis -> keep inner text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # Single-underscore italics, but only when bounded by non-word chars so
    # snake_case identifiers and URLs are left intact.
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"`{1,3}(.+?)`{1,3}", r"\1", text)
    # Markdown headings + leading bullets
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
    # Any stray leftover formatting chars
    text = text.replace("*", "").replace("`", "")
    return text


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
    """Return the small Azure OpenAI chat model (gpt-5-mini).

    temperature is accepted for compatibility but not forwarded (gpt-5 only
    supports the default).
    """
    _ = temperature
    return AzureChatOpenAI(
        azure_deployment=settings.SMALL_TEXT_MODEL_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        temperature=1,
        timeout=60.0,  # 60 second timeout to prevent hanging
        max_retries=3,  # Increased retries for flaky connections
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
    )

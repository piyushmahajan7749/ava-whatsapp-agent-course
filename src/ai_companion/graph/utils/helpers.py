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
        max_tokens=100,
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

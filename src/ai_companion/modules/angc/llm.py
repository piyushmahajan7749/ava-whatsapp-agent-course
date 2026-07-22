"""Provider-agnostic chat-completion helper for the ANGC assistant.

All task parsing goes through complete(), so the LLM vendor is swappable with
env vars alone (LLM_PROVIDER + the matching key + model names). Every supported
provider speaks the OpenAI API; only the base URL and the max-tokens parameter
name differ. Defaults to Groq — free, fast, and OpenAI-compatible.
"""

import logging

from openai import AzureOpenAI, OpenAI

from ai_companion.settings import settings

logger = logging.getLogger(__name__)

_GROQ_BASE = "https://api.groq.com/openai/v1"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _provider() -> str:
    return (settings.LLM_PROVIDER or "groq").strip().lower()


def _client():
    p = _provider()
    if p == "azure":
        return AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    if p == "gemini":
        return OpenAI(api_key=settings.GEMINI_API_KEY, base_url=_GEMINI_BASE)
    if p == "openai":
        return OpenAI(api_key=settings.OPENAI_API_KEY)
    # default: groq
    return OpenAI(api_key=settings.GROQ_API_KEY, base_url=_GROQ_BASE)


def complete(messages: list[dict], model: str, max_tokens: int = 2000, json_mode: bool = False) -> str:
    """Run a chat completion and return the message text (never None)."""
    kwargs: dict = {"model": model, "messages": messages}
    # Azure's newer API renamed max_tokens -> max_completion_tokens; the OpenAI-
    # compatible providers (Groq/OpenAI/Gemini) still use max_tokens.
    if _provider() == "azure":
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""

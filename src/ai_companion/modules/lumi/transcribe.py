"""
Audio transcription using Azure OpenAI Whisper deployment.

Downloads audio from a URL (e.g. WhatsApp voice notes) and transcribes
using the Whisper model deployed on Azure OpenAI.
"""

import logging
import tempfile
from pathlib import Path

import httpx

from ai_companion.settings import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(media_url: str) -> str | None:
    """
    Download audio from URL and transcribe using Azure Whisper.

    Args:
        media_url: URL to the audio file (e.g. Interakt media URL for voice notes)

    Returns:
        Transcribed text, or None if transcription fails.
    """
    try:
        # Download audio to a temp file
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(media_url)
            response.raise_for_status()

        # Write to temp file with .ogg extension (WhatsApp voice notes are opus/ogg)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        logger.info(f"[TRANSCRIBE] Downloaded audio: {len(response.content)} bytes")

        # Call Azure Whisper API
        whisper_url = (
            f"{settings.AZURE_OPENAI_API_ENDPOINT.rstrip('/')}"
            f"/openai/deployments/{settings.AZURE_WHISPER_DEPLOYMENT}"
            f"/audio/translations?api-version=2024-06-01"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(tmp_path, "rb") as audio_file:
                result = await client.post(
                    whisper_url,
                    headers={"api-key": settings.AZURE_OPENAI_API_KEY},
                    files={"file": ("audio.ogg", audio_file, "audio/ogg")},
                )
                result.raise_for_status()

        data = result.json()
        text = data.get("text", "").strip()

        logger.info(f"[TRANSCRIBE] Transcribed: {text[:100]}...")

        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)

        return text if text else None

    except Exception as e:
        logger.error(f"[TRANSCRIBE] Failed: {e}")
        return None

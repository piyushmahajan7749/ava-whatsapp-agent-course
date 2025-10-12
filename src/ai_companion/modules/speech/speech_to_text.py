import os
import tempfile
from typing import Optional

from ai_companion.core.exceptions import SpeechToTextError
from ai_companion.settings import settings
from groq import Groq


class SpeechToText:
    """A class to handle speech-to-text conversion using Groq's Whisper model."""

    # Required environment variables
    REQUIRED_ENV_VARS = ["GROQ_API_KEY"]

    def __init__(self):
        """Initialize the SpeechToText class and validate environment variables."""
        self._validate_env_vars()
        self._client: Optional[Groq] = None

    def _validate_env_vars(self) -> None:
        """Validate that all required environment variables are set."""
        # Check settings object instead of os.getenv (pydantic-settings loads .env into settings, not os.environ)
        missing_vars = []
        try:
            if not settings.GROQ_API_KEY:
                missing_vars.append("GROQ_API_KEY")
        except:
            missing_vars.append("GROQ_API_KEY")
            
        if missing_vars:
            import warnings
            warnings.warn(f"Missing environment variables: {', '.join(missing_vars)}. Speech-to-text will not be available.")
            self._client = None  # Set to None so we can check later
            return  # Don't raise, just warn
    @property
    def client(self) -> Groq:
        """Get or create Groq client instance using singleton pattern."""
        if self._client is None:
            self._client = Groq(api_key=settings.GROQ_API_KEY)
        return self._client

    async def transcribe(self, audio_data: bytes) -> str:
        """Convert speech to text using Groq's Whisper model.

        Args:
            audio_data: Binary audio data

        Returns:
            str: Transcribed text

        Raises:
            ValueError: If the audio file is empty or invalid
            RuntimeError: If the transcription fails
        """
        if not audio_data:
            raise ValueError("Audio data cannot be empty")

        try:
            # Create a temporary file with .wav extension
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Open the temporary file for the API request
                with open(temp_file_path, "rb") as audio_file:
                    transcription = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model="whisper-large-v3-turbo",
                        language="en",
                        response_format="text",
                    )

                if not transcription:
                    raise SpeechToTextError("Transcription result is empty")

                return transcription

            finally:
                # Clean up the temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            raise SpeechToTextError(f"Speech-to-text conversion failed: {str(e)}") from e

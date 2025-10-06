import base64
import logging
import os
from typing import Optional, Union

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage

from ai_companion.core.exceptions import ImageToTextError
from ai_companion.settings import settings


class ImageToText:
    """A class to handle image-to-text conversion using Azure OpenAI's vision capabilities."""

    REQUIRED_ENV_VARS = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_ENDPOINT"]

    def __init__(self):
        """Initialize the ImageToText class and validate environment variables."""
        self._validate_env_vars()
        self._client: Optional[AzureChatOpenAI] = None
        self.logger = logging.getLogger(__name__)

    def _validate_env_vars(self) -> None:
        """Validate that all required environment variables are set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    @property
    def client(self) -> AzureChatOpenAI:
        """Get or create Azure OpenAI client instance using singleton pattern."""
        if self._client is None:
            self._client = AzureChatOpenAI(
                azure_deployment=settings.AZURE_OPENAI_VISION_DEPLOYMENT,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                max_tokens=1000,
                timeout=60.0,
                max_retries=3,
                api_key=settings.AZURE_OPENAI_API_KEY,
                azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
            )
        return self._client

    async def analyze_image(self, image_data: Union[str, bytes], prompt: str = "") -> str:
        """Analyze an image using Azure OpenAI's vision capabilities.

        Args:
            image_data: Either a file path (str) or binary image data (bytes)
            prompt: Optional prompt to guide the image analysis

        Returns:
            str: Description or analysis of the image

        Raises:
            ValueError: If the image data is empty or invalid
            ImageToTextError: If the image analysis fails
        """
        try:
            # Handle file path
            if isinstance(image_data, str):
                if not os.path.exists(image_data):
                    raise ValueError(f"Image file not found: {image_data}")
                with open(image_data, "rb") as f:
                    image_bytes = f.read()
            else:
                image_bytes = image_data

            if not image_bytes:
                raise ValueError("Image data cannot be empty")

            # Convert image to base64
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Default prompt if none provided
            if not prompt:
                prompt = "Please describe what you see in this image in detail."

            # Create message with image for Azure OpenAI Vision using LangChain pattern
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ]
            )

            # Make the API call using LangChain's invoke pattern
            response = await self.client.ainvoke([message])

            if not response or not response.content:
                raise ImageToTextError("No response received from the vision model")

            description = response.content
            self.logger.info(f"Generated image description: {description}")

            return description

        except Exception as e:
            raise ImageToTextError(f"Failed to analyze image: {str(e)}") from e

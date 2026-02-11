"""
Interakt API Client for sending WhatsApp messages via Interakt.

This module handles:
- Sending text messages to WhatsApp numbers
- Sending interactive messages (buttons, lists)
- Logging requests/responses
- Error handling
"""

import logging
from typing import Dict, List, Optional
from functools import lru_cache

import httpx

from ai_companion.settings import settings

logger = logging.getLogger(__name__)


class InteraktClient:
    """Client for interacting with Interakt API."""

    def __init__(
        self,
        api_key: str,
        send_message_url: str,
    ):
        """
        Initialize Interakt client.

        Args:
            api_key: Interakt API key
            send_message_url: URL for sending messages
        """
        self.api_key = api_key
        self.send_message_url = send_message_url

        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"[INTERAKT] Client initialized: {self.send_message_url}")

    def _parse_phone_number(self, phone_number: str) -> tuple[str, str]:
        """
        Parse phone number into country code and local number.

        Args:
            phone_number: Phone number in E.164 format (no +), e.g., "919303402193"

        Returns:
            Tuple of (country_code, local_number)
        """
        # Remove any non-numeric characters
        phone = "".join(c for c in phone_number if c.isdigit())

        # Handle Indian numbers (most common case)
        if phone.startswith("91") and len(phone) == 12:
            return "91", phone[2:]

        # Handle US/Canada numbers
        if phone.startswith("1") and len(phone) == 11:
            return "1", phone[1:]

        # Fallback: assume first 2 digits are country code
        if len(phone) > 10:
            return phone[:2], phone[2:]

        # If 10 digits, assume India
        return "91", phone

    async def send_text_message(
        self,
        phone_number: str,
        message_text: str,
    ) -> Dict:
        """
        Send a plain text message via Interakt.

        Args:
            phone_number: User's phone number in E.164 format (no +)
            message_text: Message content to send

        Returns:
            API response dictionary
        """
        country_code, local_number = self._parse_phone_number(phone_number)

        payload = {
            "countryCode": country_code,
            "phoneNumber": local_number,
            "type": "Text",
            "data": {"message": message_text},
        }

        logger.info(f"[INTERAKT] Sending message to +{country_code}{local_number}")
        logger.debug(f"[INTERAKT] Payload: {payload}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    self.send_message_url,
                    headers=self.headers,
                    json=payload,
                )

                result = response.json() if response.content else {}
                logger.info(f"[INTERAKT] Response status: {response.status_code}")
                logger.debug(f"[INTERAKT] Response body: {result}")

                if response.status_code not in (200, 201):
                    logger.error(
                        f"[INTERAKT] Send failed: {response.status_code} - {result}"
                    )

                return {"status_code": response.status_code, "response": result}

            except httpx.HTTPError as e:
                logger.error(f"[INTERAKT] HTTP error: {e}")
                raise

    async def send_button_message(
        self,
        phone_number: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ) -> Dict:
        """
        Send an interactive button message via Interakt.

        Args:
            phone_number: User's phone number in E.164 format (no +)
            body_text: Main message body
            buttons: List of button dicts with "id" and "title" keys
            header_text: Optional header text
            footer_text: Optional footer text

        Returns:
            API response dictionary
        """
        country_code, local_number = self._parse_phone_number(phone_number)

        # Build button actions
        button_actions = []
        for btn in buttons[:3]:  # WhatsApp allows max 3 buttons
            button_actions.append(
                {"type": "reply", "reply": {"id": btn["id"], "title": btn["title"][:20]}}
            )

        # Interakt requires "message" to be a nested object following WhatsApp's
        # interactive message schema (not a plain string).
        interactive_message = {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": button_actions},
        }

        if header_text:
            interactive_message["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive_message["footer"] = {"text": footer_text}

        payload = {
            "countryCode": country_code,
            "phoneNumber": local_number,
            "type": "InteractiveButton",
            "data": {
                "message": interactive_message,
            },
        }

        logger.info(f"[INTERAKT] Sending button message to +{country_code}{local_number}")
        logger.debug(f"[INTERAKT] Payload: {payload}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    self.send_message_url,
                    headers=self.headers,
                    json=payload,
                )

                result = response.json() if response.content else {}
                logger.info(f"[INTERAKT] Response status: {response.status_code}")

                if response.status_code not in (200, 201):
                    logger.error(
                        f"[INTERAKT] Send failed: {response.status_code} - {result}"
                    )

                return {"status_code": response.status_code, "response": result}

            except httpx.HTTPError as e:
                logger.error(f"[INTERAKT] HTTP error: {e}")
                raise

    async def send_list_message(
        self,
        phone_number: str,
        body_text: str,
        button_text: str,
        sections: List[Dict],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None,
    ) -> Dict:
        """
        Send an interactive list message via Interakt.

        Args:
            phone_number: User's phone number in E.164 format (no +)
            body_text: Main message body
            button_text: Text on the list button
            sections: List of section dicts with "title" and "rows" keys
            header_text: Optional header text
            footer_text: Optional footer text

        Returns:
            API response dictionary
        """
        country_code, local_number = self._parse_phone_number(phone_number)

        # Interakt requires "message" to be a nested object following WhatsApp's
        # interactive message schema (same as button messages).
        interactive_message = {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": sections,
            },
        }

        if header_text:
            interactive_message["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive_message["footer"] = {"text": footer_text}

        payload = {
            "countryCode": country_code,
            "phoneNumber": local_number,
            "type": "InteractiveList",
            "data": {
                "message": interactive_message,
            },
        }

        logger.info(f"[INTERAKT] Sending list message to +{country_code}{local_number}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    self.send_message_url,
                    headers=self.headers,
                    json=payload,
                )

                result = response.json() if response.content else {}

                if response.status_code not in (200, 201):
                    logger.error(
                        f"[INTERAKT] Send failed: {response.status_code} - {result}"
                    )

                return {"status_code": response.status_code, "response": result}

            except httpx.HTTPError as e:
                logger.error(f"[INTERAKT] HTTP error: {e}")
                raise

    async def tag_user(
        self,
        phone_number: str,
        tags: List[str],
    ) -> Dict:
        """
        Add tags/labels to a user in Interakt via Track Users API.

        Tags are add-only — they append to existing tags, never replace.

        Args:
            phone_number: User's phone number in E.164 format (no +), e.g., "919303402193"
            tags: List of tag strings, e.g., ["Warm Lead Close ASAP"]

        Returns:
            API response dictionary
        """
        country_code, local_number = self._parse_phone_number(phone_number)

        payload = {
            "phoneNumber": local_number,
            "countryCode": f"+{country_code}",
            "tags": tags,
        }

        track_url = "https://api.interakt.ai/v1/public/track/users/"

        logger.info(f"[INTERAKT] Tagging user +{country_code}{local_number} with {tags}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    track_url,
                    headers=self.headers,
                    json=payload,
                )

                result = response.json() if response.content else {}
                logger.info(f"[INTERAKT] Tag response status: {response.status_code}")

                if response.status_code not in (200, 201, 202):
                    logger.error(
                        f"[INTERAKT] Tag failed: {response.status_code} - {result}"
                    )

                return {"status_code": response.status_code, "response": result}

            except httpx.HTTPError as e:
                logger.error(f"[INTERAKT] HTTP error tagging user: {e}")
                raise


@lru_cache(maxsize=1)
def get_interakt_client() -> Optional[InteraktClient]:
    """
    Get singleton Interakt client instance.

    Returns:
        InteraktClient if configured, None if not configured
    """
    api_key = settings.INTERAKT_API_KEY
    send_message_url = settings.INTERAKT_SEND_MESSAGE_URL

    if not api_key:
        logger.warning("[INTERAKT] Integration not configured (missing INTERAKT_API_KEY)")
        return None

    return InteraktClient(
        api_key=api_key,
        send_message_url=send_message_url,
    )

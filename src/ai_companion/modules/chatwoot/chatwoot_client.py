"""
Chatwoot API Client for managing conversations and messages.

This module handles:
- Contact creation and retrieval
- Conversation management
- Message forwarding to Chatwoot UI
- Human handoff detection
"""

import logging
import os
from typing import Dict, List, Optional
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)


class ChatwootClient:
    """Client for interacting with Chatwoot API."""
    
    def __init__(
        self,
        api_url: str,
        api_token: str,
        account_id: int = 1,
        inbox_id: Optional[int] = None,
    ):
        """
        Initialize Chatwoot client.
        
        Args:
            api_url: Chatwoot API base URL (e.g., https://chat.upaai.in/api/v1)
            api_token: API access token
            account_id: Account ID (usually 1 for single account)
            inbox_id: Default inbox ID for WhatsApp messages
        """
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.account_id = account_id
        self.inbox_id = inbox_id
        
        self.headers = {
            "api_access_token": self.api_token,
            "Content-Type": "application/json",
        }
        
        logger.info(f"Chatwoot client initialized: {self.api_url}, account={self.account_id}")
    
    async def get_or_create_contact(
        self,
        phone_number: str,
        name: Optional[str] = None,
    ) -> Dict:
        """
        Get existing contact or create new one by phone number.
        
        Args:
            phone_number: WhatsApp phone number with country code (e.g., +919131036482)
            name: Optional contact name
            
        Returns:
            Contact dictionary with id, name, phone_number, etc.
        """
        # Normalize phone number (remove spaces, ensure + prefix)
        phone = phone_number.strip()
        if not phone.startswith('+'):
            phone = '+' + phone
        
        # Search for existing contact
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_url = f"{self.api_url}/accounts/{self.account_id}/contacts/search"
            params = {"q": phone}
            
            try:
                response = await client.get(search_url, headers=self.headers, params=params)
                response.raise_for_status()
                
                contacts = response.json().get("payload", [])
                
                # Check if contact exists
                for contact in contacts:
                    if contact.get("phone_number") == phone:
                        logger.debug(f"Found existing contact: {contact['id']} for {phone}")
                        return contact
                
                # Create new contact if not found
                logger.info(f"Creating new contact for {phone}")
                create_url = f"{self.api_url}/accounts/{self.account_id}/contacts"
                payload = {
                    "phone_number": phone,
                    "name": name or f"User {phone[-4:]}",
                }
                
                create_response = await client.post(
                    create_url,
                    headers=self.headers,
                    json=payload
                )
                create_response.raise_for_status()
                
                contact = create_response.json().get("payload", {}).get("contact", {})
                logger.info(f"Created contact: {contact.get('id')} for {phone}")
                return contact
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to get/create contact for {phone}: {e}")
                raise
    
    async def get_or_create_conversation(
        self,
        contact_id: int,
        inbox_id: Optional[int] = None,
    ) -> Dict:
        """
        Get or create a conversation for a contact in an inbox.
        
        Args:
            contact_id: Chatwoot contact ID
            inbox_id: Inbox ID (uses default if not provided)
            
        Returns:
            Conversation dictionary with id, status, assignee_id, etc.
        """
        inbox = inbox_id or self.inbox_id
        if not inbox:
            raise ValueError("inbox_id is required")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Search for existing open or pending conversation
            list_url = f"{self.api_url}/accounts/{self.account_id}/conversations"
            params = {
                "inbox_id": inbox,
                "status": "open",  # Get open conversations
            }
            
            try:
                response = await client.get(list_url, headers=self.headers, params=params)
                response.raise_for_status()
                
                conversations = response.json().get("data", {}).get("payload", [])
                
                # Find conversation for this contact
                for conv in conversations:
                    if conv.get("meta", {}).get("sender", {}).get("id") == contact_id:
                        logger.debug(f"Found existing conversation: {conv['id']}")
                        return conv
                
                # Check pending conversations
                params["status"] = "pending"
                response = await client.get(list_url, headers=self.headers, params=params)
                response.raise_for_status()
                
                conversations = response.json().get("data", {}).get("payload", [])
                for conv in conversations:
                    if conv.get("meta", {}).get("sender", {}).get("id") == contact_id:
                        logger.debug(f"Found existing pending conversation: {conv['id']}")
                        return conv
                
                # Create new conversation
                logger.info(f"Creating new conversation for contact {contact_id}")
                create_url = f"{self.api_url}/accounts/{self.account_id}/conversations"
                payload = {
                    "source_id": f"whatsapp_{contact_id}",
                    "inbox_id": inbox,
                    "contact_id": contact_id,
                    "status": "pending",
                }
                
                create_response = await client.post(
                    create_url,
                    headers=self.headers,
                    json=payload
                )
                create_response.raise_for_status()
                
                conversation = create_response.json()
                logger.info(f"Created conversation: {conversation.get('id')}")
                return conversation
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to get/create conversation for contact {contact_id}: {e}")
                raise
    
    async def create_message(
        self,
        conversation_id: int,
        content: str,
        message_type: str = "incoming",
        private: bool = False,
        sender_type: str = "contact",
    ) -> Dict:
        """
        Create a message in a conversation.
        
        Args:
            conversation_id: Conversation ID
            content: Message text content
            message_type: "incoming" (from user) or "outgoing" (from bot/agent)
            private: Whether message is private (notes)
            sender_type: "contact" (user) or "agent_bot" (AI assistant)
            
        Returns:
            Created message dictionary
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{self.api_url}/accounts/{self.account_id}/conversations/{conversation_id}/messages"
            
            payload = {
                "content": content,
                "message_type": message_type,
                "private": private,
            }
            
            # Add sender type for bot messages
            if sender_type == "agent_bot":
                payload["content_attributes"] = {"ai_generated": True}
            
            try:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                
                message = response.json()
                logger.debug(f"Created {message_type} message in conversation {conversation_id}")
                return message
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to create message in conversation {conversation_id}: {e}")
                raise
    
    async def get_conversation(self, conversation_id: int) -> Dict:
        """
        Get conversation details including assignee status.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation dictionary
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{self.api_url}/accounts/{self.account_id}/conversations/{conversation_id}"
            
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to get conversation {conversation_id}: {e}")
                raise
    
    async def should_ai_respond(self, conversation_id: int) -> bool:
        """
        Check if AI should respond to this conversation.
        
        AI should NOT respond if:
        - Conversation status is "open" (human is handling it)
        - Conversation has an assignee (human agent assigned)
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if AI should respond, False if human has taken over
        """
        try:
            conversation = await self.get_conversation(conversation_id)
            
            status = conversation.get("status", "pending")
            assignee_id = conversation.get("meta", {}).get("assignee", {}).get("id")
            
            # If status is "open" or there's an assignee, human has taken over
            if status == "open" or assignee_id:
                logger.info(
                    f"Conversation {conversation_id} has human handling "
                    f"(status={status}, assignee={assignee_id}) - AI will not respond"
                )
                return False
            
            # Status is "pending" or "resolved" and no assignee - AI can respond
            return True
            
        except Exception as e:
            logger.error(f"Error checking conversation status {conversation_id}: {e}")
            # On error, default to allowing AI (fail open)
            return True
    
    async def forward_incoming_message(
        self,
        phone_number: str,
        message_text: str,
        contact_name: Optional[str] = None,
    ) -> tuple[int, int]:
        """
        Forward an incoming WhatsApp message to Chatwoot.
        
        Args:
            phone_number: User's WhatsApp phone number
            message_text: Message content
            contact_name: Optional contact name
            
        Returns:
            Tuple of (contact_id, conversation_id)
        """
        try:
            # Get or create contact
            contact = await self.get_or_create_contact(phone_number, contact_name)
            contact_id = contact.get("id")
            
            # Get or create conversation
            conversation = await self.get_or_create_conversation(contact_id)
            conversation_id = conversation.get("id")
            
            # Create incoming message
            await self.create_message(
                conversation_id=conversation_id,
                content=message_text,
                message_type="incoming",
                sender_type="contact",
            )
            
            logger.info(f"Forwarded message to Chatwoot: conversation {conversation_id}")
            return contact_id, conversation_id
            
        except Exception as e:
            logger.error(f"Failed to forward message to Chatwoot: {e}")
            raise
    
    async def forward_ai_reply(
        self,
        conversation_id: int,
        reply_text: str,
    ) -> Dict:
        """
        Forward AI-generated reply to Chatwoot as outgoing message.
        
        Args:
            conversation_id: Chatwoot conversation ID
            reply_text: AI reply content
            
        Returns:
            Created message dictionary
        """
        try:
            message = await self.create_message(
                conversation_id=conversation_id,
                content=f"🤖 AI Assistant:\n\n{reply_text}",
                message_type="outgoing",
                sender_type="agent_bot",
            )
            
            logger.info(f"Forwarded AI reply to Chatwoot: conversation {conversation_id}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to forward AI reply to Chatwoot: {e}")
            raise


@lru_cache(maxsize=1)
def get_chatwoot_client() -> Optional[ChatwootClient]:
    """
    Get singleton Chatwoot client instance.
    
    Returns:
        ChatwootClient if configured, None if Chatwoot integration is disabled
    """
    api_url = os.getenv("CHATWOOT_API_URL")
    api_token = os.getenv("CHATWOOT_API_TOKEN")
    inbox_id = os.getenv("CHATWOOT_INBOX_ID")
    account_id = int(os.getenv("CHATWOOT_ACCOUNT_ID", "1"))
    
    if not api_url or not api_token:
        logger.warning("Chatwoot integration not configured (missing API_URL or API_TOKEN)")
        return None
    
    if not inbox_id:
        logger.warning("Chatwoot INBOX_ID not configured")
        return None
    
    return ChatwootClient(
        api_url=api_url,
        api_token=api_token,
        account_id=account_id,
        inbox_id=int(inbox_id),
    )


"""
AI-based intent classification for conversation routing.

This module provides intelligent intent classification using AI instead of
keyword-based matching, offering better accuracy and context understanding.
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class IntentClassification:
    """Result of intent classification."""
    response_type: str  # 'conversation', 'audio', 'image'
    primary_intent: str  # 'booking', 'consultation_inquiry', 'products_pooja', 'general', 'escalation_needed'
    secondary_intent: Optional[str]  # Secondary intent if multiple goals detected
    confidence: float  # 0.0 to 1.0
    conversation_stage: str  # 'inquiry', 'interested', 'payment_pending', etc.
    reasoning: str  # Brief explanation of the classification


def classify_intent_with_ai(
    user_message: str, 
    conversation_history: List[str] = None,
    has_audio: bool = False,
    has_image: bool = False
) -> IntentClassification:
    """
    Use AI to classify user intent and conversation stage.
    
    Args:
        user_message: The current user message
        conversation_history: Previous messages in the conversation
        has_audio: Whether the user sent an audio message
        has_image: Whether the user sent an image
        
    Returns:
        IntentClassification with all routing information
    """
    # Build conversation context
    conversation_context = ""
    if conversation_history:
        conversation_context = "\n".join([f"User: {msg}" for msg in conversation_history[-5:]])  # Last 5 messages
        conversation_context += f"\nUser: {user_message}"
    else:
        conversation_context = f"User: {user_message}"
    
    # Create comprehensive AI prompt for intent classification
    ai_prompt = f"""
You are an intelligent routing system for Uma, a customer support agent at Upaai.in (spiritual consultation and puja booking platform).

**CONVERSATION CONTEXT:**
{conversation_context}

**MESSAGE TYPE INDICATORS:**
- Audio message: {has_audio}
- Image message: {has_image}

**YOUR TASK:**
Analyze the user's message and conversation context to determine:
1. **Media Type**: What type of response format to use
2. **Primary Intent**: What the user primarily wants
3. **Secondary Intent**: If the user has multiple goals in one message
4. **Confidence**: How certain you are about the intent classification
5. **Conversation Stage**: Where the user is in their customer journey

**INTENT CATEGORIES:**

**'booking'** - Calendar scheduling and appointment booking
- User wants to schedule, book, or check availability
- Examples: "I want to book a consultation", "Are you available tomorrow?", "Book me for next Tuesday"

**'consultation_inquiry'** - Questions about services, pricing, process
- User asking about what services are offered, how they work, pricing
- Examples: "Who is Guru Maa?", "What services do you offer?", "How much is a consultation?"

**'products_pooja'** - Product inquiries and puja bookings
- User asking about spiritual products (Kalawa, Yantra) or specific pujas
- Examples: "Tell me about Kalawa", "I want to book a Kaal Sarp Dosh puja", "What pujas do you offer?"

**'general'** - Small talk, greetings, off-topic, relationship building
- Casual conversation, greetings, non-business related
- Examples: "Hello, how are you?", "What are you doing now?", "Tell me a joke"

**'escalation_needed'** - Refunds, complaints, complex issues requiring human intervention
- User requesting refunds, complaining, asking for human help
- Examples: "I want a refund", "This is unacceptable", "Can I speak to a real person?"

**CONVERSATION STAGES:**

**'inquiry'** - Just starting, asking questions
- First-time questions, exploring services, information gathering

**'interested'** - Showing buying intent
- Expressing interest in booking/buying, asking about pricing, comparing options

**'payment_pending'** - Ready to pay but hasn't yet
- Asked about payment methods, requested QR code, said "I'll pay"

**'payment_verified'** - Payment screenshot received and verified
- User sent payment screenshot, payment detected in conversation

**'booking_ready'** - Ready to finalize booking
- Payment verified + collecting details (name, DOB), about to book in calendar

**'confirmed'** - Booking/order completed
- Appointment booked successfully, order placed successfully

**'general_chat'** - Casual conversation, no transaction intent
- Small talk, greetings, off-topic discussion

**'escalation_requested'** - User needs human assistance
- Refund request made, complaint filed, human representative requested

**RESPONSE FORMAT:**
Return a JSON object with the following structure:
{{
    "response_type": "conversation|audio|image",
    "primary_intent": "booking|consultation_inquiry|products_pooja|general|escalation_needed",
    "secondary_intent": "booking|consultation_inquiry|products_pooja|general|escalation_needed|null",
    "confidence": 0.0-1.0,
    "conversation_stage": "inquiry|interested|payment_pending|payment_verified|booking_ready|confirmed|general_chat|escalation_requested",
    "reasoning": "Brief explanation of your classification decision"
}}

**IMPORTANT RULES:**
1. Always analyze the full conversation context, not just the last message
2. Payment screenshots always indicate 'booking' intent + 'payment_verified' stage
3. Audio messages should get 'audio' response_type
4. When in doubt between intents, choose based on the most actionable request
5. Confidence should reflect ambiguity - don't always give high confidence
6. Stage should reflect progression - track user journey accurately
7. Escalation takes PRIORITY over other intents when user is making actual requests/complaints

**EXAMPLES:**

User: "I want to book a consultation with Guru Maa"
Response: {{"response_type": "conversation", "primary_intent": "booking", "secondary_intent": null, "confidence": 0.95, "conversation_stage": "interested", "reasoning": "User explicitly wants to book a consultation. Clear booking intent with high confidence."}}

User: "Tell me about Kaal Sarp Dosh puja and the price, and can I book it for next week?"
Response: {{"response_type": "conversation", "primary_intent": "products_pooja", "secondary_intent": "booking", "confidence": 0.85, "conversation_stage": "interested", "reasoning": "Hybrid intent detected. Primary focus is learning about the puja, but user also wants to schedule."}}

User: "Here's my payment screenshot [Image attached]"
Response: {{"response_type": "conversation", "primary_intent": "booking", "secondary_intent": null, "confidence": 1.0, "conversation_stage": "payment_verified", "reasoning": "User submitted payment screenshot. This is part of booking workflow."}}

User: "Hello! How are you doing today?"
Response: {{"response_type": "conversation", "primary_intent": "general", "secondary_intent": null, "confidence": 1.0, "conversation_stage": "general_chat", "reasoning": "Casual greeting with no business intent."}}

Now analyze the conversation and return your classification as JSON.
"""

    try:
        # Import here to avoid circular dependency
        from ai_companion.graph.utils.helpers import get_chat_model
        
        # Get the chat model
        model = get_chat_model()
        
        # Get AI response
        response = model.invoke(ai_prompt)
        
        # Extract the content from the response
        if hasattr(response, 'content'):
            ai_response = response.content
        else:
            ai_response = str(response)
        
        # Parse JSON response
        try:
            # Clean up the response to extract JSON
            ai_response = ai_response.strip()
            if ai_response.startswith('```json'):
                ai_response = ai_response[7:]
            if ai_response.endswith('```'):
                ai_response = ai_response[:-3]
            ai_response = ai_response.strip()
            
            # Parse the JSON
            result = json.loads(ai_response)
            
            # Validate and create IntentClassification
            return IntentClassification(
                response_type=result.get('response_type', 'conversation'),
                primary_intent=result.get('primary_intent', 'general'),
                secondary_intent=result.get('secondary_intent'),
                confidence=float(result.get('confidence', 0.5)),
                conversation_stage=result.get('conversation_stage', 'inquiry'),
                reasoning=result.get('reasoning', 'AI classification completed')
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback to basic classification if AI response is malformed
            return _fallback_classification(user_message, has_audio, has_image)
            
    except Exception as e:
        # Fallback to basic classification if AI fails
        print(f"AI intent classification failed: {e}, using fallback")
        return _fallback_classification(user_message, has_audio, has_image)


def _fallback_classification(user_message: str, has_audio: bool, has_image: bool) -> IntentClassification:
    """
    Fallback classification using simple keyword matching.
    Used when AI classification fails.
    """
    message_lower = user_message.lower()
    
    # Determine response type
    if has_audio:
        response_type = "audio"
    elif has_image:
        response_type = "conversation"  # Images are handled in conversation
    else:
        response_type = "conversation"
    
    # Simple keyword-based intent detection
    if any(word in message_lower for word in ["book", "appointment", "schedule", "available", "slot", "time", "date"]):
        primary_intent = "booking"
        conversation_stage = "interested"
    elif any(word in message_lower for word in ["refund", "complaint", "dissatisfied", "not happy", "manager", "human"]):
        primary_intent = "escalation_needed"
        conversation_stage = "escalation_requested"
    elif any(word in message_lower for word in ["kalawa", "yantra", "pooja", "puja", "temple", "product"]):
        primary_intent = "products_pooja"
        conversation_stage = "inquiry"
    elif any(word in message_lower for word in ["what", "how", "who", "tell me", "consultation", "service"]):
        primary_intent = "consultation_inquiry"
        conversation_stage = "inquiry"
    else:
        primary_intent = "general"
        conversation_stage = "general_chat"
    
    return IntentClassification(
        response_type=response_type,
        primary_intent=primary_intent,
        secondary_intent=None,
        confidence=0.6,  # Lower confidence for fallback
        conversation_stage=conversation_stage,
        reasoning="Fallback classification using keyword matching"
    )

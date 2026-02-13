"""
Lumi onboarding flow handler.

Manages stage transitions, processes user input, and generates responses
for the 15-stage onboarding flow using LLM for natural conversations.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timedelta
from typing import List, Optional

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from ai_companion.settings import settings
from ai_companion.modules.lumi.state import (
    OnboardingStage,
    LumiUserState,
    get_user_state,
    save_user_state,
)
from ai_companion.modules.lumi.prompts import (
    LUMI_PERSONA,
    STAGE_MESSAGES,
    THERAPY_HISTORY_FOLLOWUPS,
    STORY_ACKNOWLEDGMENTS,
    CARE_PREFERENCE_NOT_SURE,
    MEDICATION_YES_FOLLOWUP,
    THERAPIST_STYLE_NOT_SURE,
    FRICTION_CYCLING_OPTIONS,
    HUMAN_HANDOFF_MESSAGE,
    CRISIS_RESPONSE,
    FAQ_SYSTEM_PROMPT_SECTION,
    WHATSAPP_COMMUNITY_CTA,
    EXPERT_DIRECTORY_CTA,
)
from ai_companion.modules.lumi.crisis_detector import check_for_crisis
from ai_companion.modules.lumi.friction_detector import check_for_friction
from ai_companion.modules.lumi.matching import (
    match_therapist,
    get_alternative_therapists,
    format_therapist_card,
    format_alternative_card,
)
from ai_companion.modules.lumi.consultation import (
    get_consultation_client,
    get_upcoming_dates,
    format_time_label,
)
from ai_companion.modules.handoff import should_handoff

logger = logging.getLogger(__name__)


def _get_lumi_llm():
    """Get the LLM for Lumi responses."""
    # Note: gpt-5.2 reasoning model only supports temperature=1
    return AzureChatOpenAI(
        azure_deployment=settings.TEXT_MODEL_NAME,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        temperature=1.0,
        timeout=30.0,
        max_retries=2,
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_API_ENDPOINT,
    )


# Stage guidance for LLM
STAGE_GUIDANCE = {
    OnboardingStage.WELCOME: """The user just replied to your welcome message. Acknowledge their response warmly in 1-2 sentences, then ask how they're doing today or what's on their mind. Keep it open-ended and casual. Do NOT mention options or next steps yet.""",

    OnboardingStage.WARMUP: """The user shared how they're doing. Acknowledge what they said warmly and ask a gentle follow-up to understand a bit more about what's going on for them. Keep it open-ended and conversational. One question only.""",

    OnboardingStage.WARMUP_2: """The user shared more about what's going on. Acknowledge and validate what they said in 1-2 sentences. Then let them know you can help in a few different ways. Do NOT list the options explicitly, buttons will be shown automatically.""",

    OnboardingStage.DEMOGRAPHICS: """Ask about their age and gender identity in a friendly, casual way. Keep it brief - just one or two questions.""",

    OnboardingStage.STORY: """Ask what brings them here today. Be warm and open. Let them know they can type or send a voice note - whatever feels easier.""",

    OnboardingStage.THERAPY_HISTORY: """Ask if they've tried therapy before. Be curious but non-judgmental. Do NOT list options, buttons will be shown automatically.""",

    OnboardingStage.CARE_PREFERENCES: """Ask what kind of support feels right for them. Do NOT list the options, buttons will be shown automatically.""",

    OnboardingStage.MEDICATION: """Ask if they're currently taking any mental health medications. Be gentle and reassure this is just to help with matching. Do NOT list options, buttons will be shown automatically.""",

    OnboardingStage.CONCERNS: """Ask what they're hoping to work on. Mention a few examples naturally (like anxiety, depression, relationships). Let them know they can select multiple.""",

    OnboardingStage.LANGUAGE: """Ask their preferred language for therapy. Mention a couple of common options naturally. Do NOT list all options, buttons will be shown automatically.""",

    OnboardingStage.THERAPIST_STYLE: """Ask about their preferred therapist style. Mention a couple of examples naturally. Do NOT list all options.""",

    OnboardingStage.GENDER_PREFERENCE: """Ask if they have a preference for their therapist's gender. Do NOT list options, buttons will be shown automatically.""",

    OnboardingStage.PERSONAL_CONTEXT: """Ask about their relationship status. Keep it casual. Do NOT list options, buttons will be shown automatically.""",

    OnboardingStage.PERSONAL_CITY: """Ask which city they're based in.""",

    OnboardingStage.PROCESSING: """Let them know you're finding the right match. Build some anticipation.""",

    OnboardingStage.MATCH_REVEAL: """Present the matched therapist enthusiastically. Include their name, bio, and why they're a good match. Ask if they want to book or see other options.""",

    OnboardingStage.BOOKING: """Ask them to confirm they understand this isn't a diagnosis and that the team may contact them. Get their confirmation to proceed.""",

    OnboardingStage.CONFIRMED: """Celebrate! Confirm the booking, share next steps, and let them know the care team will reach out.""",

    OnboardingStage.BROWSE_EXPERTS: """The user chose to browse experts on their own and you sent them the directory link. Answer any questions they have about experts, pricing, how therapy works, etc. Be helpful and warm. If they want more help, let them know they can always come back.""",

    OnboardingStage.CONSULTATION_INTRO: """The user mentioned when they're available for a consultation call. Acknowledge their preference in 1 sentence, then let them know you'll show them available slots. Keep it brief.""",

    OnboardingStage.ROUTE_SELECT: """The user saw route options. Process their choice: browse experts, talk to specialist, or continue with Lumi.""",

    OnboardingStage.CONSULTATION_DATE: """The user is picking a date for a consultation call. Help them choose.""",

    OnboardingStage.CONSULTATION_TIME_SECTION: """The user is choosing a time of day (Morning, Afternoon, or Evening) for their consultation call.""",

    OnboardingStage.CONSULTATION_TIME: """The user is picking a time slot for their consultation. Help them choose.""",

    OnboardingStage.PREFERENCES_COLLECTED: """All data has been collected. Let the user know a Care Specialist will reach out.""",
}


@dataclass
class FlowResponse:
    """Response from flow handler."""

    messages: List[str]
    buttons: Optional[List[dict]] = None
    list_options: Optional[dict] = None  # {"button_text": str, "sections": list}
    friction_message: Optional[str] = None
    friction_buttons: Optional[List[dict]] = None
    is_handoff: bool = False
    handoff_reason: Optional[str] = None
    is_crisis: bool = False
    new_state: Optional[LumiUserState] = None


TERMINAL_STAGES = {
    OnboardingStage.CONFIRMED,
    OnboardingStage.HUMAN_HANDOFF,
    OnboardingStage.ARCHIVED,
    OnboardingStage.CONSULTATION_CONFIRMED,
    OnboardingStage.PREFERENCES_COLLECTED,
}


class LumiFlowHandler:
    """Handler for Lumi onboarding conversation flow with LLM integration."""

    CONCERN_KEYWORDS = {
        "anxiety": ["anxiety", "anxious", "worried", "panic", "nervous"],
        "depression": ["depression", "depressed", "sad", "hopeless", "low mood"],
        "trauma": ["trauma", "ptsd", "abuse", "assault", "accident"],
        "relationship": ["relationship", "partner", "marriage", "divorce", "breakup"],
        "burnout": ["burnout", "exhausted", "overworked", "tired", "stressed"],
        "grief": ["grief", "loss", "death", "died", "mourning"],
        "stress": ["stress", "overwhelmed", "pressure", "tense"],
    }

    def __init__(self):
        """Initialize flow handler."""
        self.llm = _get_lumi_llm()
        logger.info("[LUMI_FLOW] Handler initialized with LLM")

    async def handle_message(
        self,
        phone_number: str,
        message_text: str,
        is_button_response: bool = False,
    ) -> FlowResponse:
        """Process incoming message and generate response."""
        # Get or create user state
        state = get_user_state(phone_number)
        is_new_user = state is None

        if is_new_user:
            state = LumiUserState(phone_number=phone_number)
            logger.info(f"[LUMI_FLOW] New user: {phone_number}")
            # For new users, send welcome message first
            welcome_response = await self._generate_welcome(state, message_text)
            save_user_state(state)
            return welcome_response

        # Terminal states: conversation is over, do not respond
        if state.stage in TERMINAL_STAGES:
            logger.info(
                f"[LUMI_FLOW] Ignoring message from {phone_number} - "
                f"conversation is in terminal state: {state.stage}"
            )
            return FlowResponse(messages=[])

        # Update last message timestamp
        state.last_message_at = datetime.now()

        # Add user message to history
        state.conversation_history.append({
            "role": "user",
            "content": message_text,
            "timestamp": datetime.now().isoformat()
        })

        # Check for crisis first (always)
        crisis_decision = check_for_crisis(message_text)
        if crisis_decision.is_crisis:
            logger.warning(f"[LUMI_FLOW] CRISIS detected for {phone_number}")
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = f"crisis: {crisis_decision.matched_pattern}"
            save_user_state(state)
            return FlowResponse(
                messages=[CRISIS_RESPONSE],
                is_crisis=True,
                is_handoff=True,
                handoff_reason="crisis",
                new_state=state,
            )

        # Check for handoff keywords — skip at stages where "talk to care team"
        # or "browse experts" are expected button actions, not genuine handoff requests
        if state.stage not in (
            OnboardingStage.ROUTE_SELECT,
            OnboardingStage.WARMUP,
            OnboardingStage.WARMUP_2,
            OnboardingStage.BROWSE_EXPERTS,
            OnboardingStage.CONSULTATION_INTRO,
            OnboardingStage.CONSULTATION_DATE,
            OnboardingStage.CONSULTATION_TIME_SECTION,
            OnboardingStage.CONSULTATION_TIME,
            OnboardingStage.MATCH_REVEAL,
            OnboardingStage.ALTERNATIVE_THERAPISTS,
        ):
            handoff_decision = should_handoff(message_text)
            if handoff_decision.should_handoff:
                logger.info(f"[LUMI_FLOW] Handoff triggered: {handoff_decision.reason}")
                state.stage = OnboardingStage.HUMAN_HANDOFF
                state.handoff_reason = handoff_decision.reason
                save_user_state(state)
                return FlowResponse(
                    messages=[
                        HUMAN_HANDOFF_MESSAGE,
                        "I'm handing you over to our Care team now. If you need me again, just send a message anytime!",
                    ],
                    is_handoff=True,
                    handoff_reason=handoff_decision.reason,
                    new_state=state,
                )

        # Check for friction
        friction_decision = check_for_friction(
            message_text,
            stage=state.stage,
            last_message_at=state.last_message_at,
            short_answer_count=state.short_answer_count,
            friction_count=state.friction_detected_count,
        )
        if friction_decision.is_friction:
            state.friction_detected_count += 1
            if friction_decision.friction_type == "short_answer":
                state.short_answer_count += 1

        # Handle CTA button selections (community, vitality score, directory, etc.)
        button_response = self._handle_button_action(state, message_text)
        if button_response is not None:
            save_user_state(state)
            return button_response

        # Process based on current stage
        response = await self._process_stage(state, message_text, is_button_response)

        # Add AI response to history
        for msg in response.messages:
            state.conversation_history.append({
                "role": "assistant",
                "content": msg,
                "timestamp": datetime.now().isoformat()
            })

        # Limit history to last 20 messages to prevent token overflow
        if len(state.conversation_history) > 20:
            state.conversation_history = state.conversation_history[-20:]

        save_user_state(state)
        response.new_state = state
        return response

    async def _generate_welcome(self, state: LumiUserState, user_message: str) -> FlowResponse:
        """Generate welcome message for new users using fixed template."""
        state.stage = OnboardingStage.WELCOME

        # Add user's initial message to history
        state.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })

        # Use fixed welcome message for consistency
        welcome_text = STAGE_MESSAGES[OnboardingStage.WELCOME]

        # Add to history
        state.conversation_history.append({
            "role": "assistant",
            "content": welcome_text,
            "timestamp": datetime.now().isoformat()
        })

        # Stay at WELCOME stage — let the user respond to "Sound good?" first.
        # Route selection buttons will be shown after the user replies.

        return FlowResponse(
            messages=[welcome_text],
        )

    async def _generate_llm_response(self, state: LumiUserState, user_message: str) -> str:
        """Generate a response using the LLM with conversation context."""

        # Build system prompt with persona and stage guidance
        stage = state.stage
        stage_guidance = STAGE_GUIDANCE.get(stage, "Continue the conversation naturally.")

        # Include user context in system prompt
        user_context = self._build_user_context(state)

        stage_name = stage.value if hasattr(stage, 'value') else str(stage)

        system_prompt = f"""{LUMI_PERSONA}

Current stage: {stage_name}
Stage guidance: {stage_guidance}

User context:
{user_context}

IMPORTANT RULES:
- Keep responses SHORT (2-3 sentences max)
- Be warm but concise
- Ask ONLY ONE question per message. Never combine two topics.
- Do NOT list options or bullet points for choices. Buttons will be shown separately by the system.
- Never diagnose or give medical advice
- Respond naturally to what the user said
- Do NOT use emojis unless there is a strong reason (first greeting, celebration moment). Most messages should have zero emojis.
- NEVER repeat a phrase, emoji, or sign-off you already used in this conversation. Vary your language every time.
- Do NOT fall into patterns like always ending with a heart, always starting with "I hear you", etc.
- Never use em dashes or long dashes. Use commas, periods, or colons instead.

{FAQ_SYSTEM_PROMPT_SECTION}
"""

        # Build messages for LLM
        messages = [SystemMessage(content=system_prompt)]

        # Add conversation history (last 10 messages for context)
        for msg in state.conversation_history[-10:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

        # Generate response
        try:
            response = await self.llm.ainvoke(messages)
            text = response.content.strip()
            # Replace em dashes and en dashes with regular hyphens
            text = text.replace("—", "-").replace("–", "-")
            return text
        except Exception as e:
            logger.error(f"[LUMI_FLOW] LLM invoke error: {e}")
            raise

    def _build_user_context(self, state: LumiUserState) -> str:
        """Build context string from collected user data."""
        context_parts = []

        if state.age:
            context_parts.append(f"Age: {state.age}")
        if state.gender:
            context_parts.append(f"Gender: {state.gender}")
        if state.story_text:
            context_parts.append(f"Their story: {state.story_text[:200]}...")
        if state.therapy_history:
            context_parts.append(f"Therapy history: {state.therapy_history}")
        if state.care_preference:
            context_parts.append(f"Care preference: {state.care_preference}")
        if state.concerns:
            context_parts.append(f"Concerns: {', '.join(state.concerns)}")
        if state.language:
            context_parts.append(f"Language: {state.language}")
        if state.therapist_style:
            context_parts.append(f"Therapist style: {', '.join(state.therapist_style)}")
        if state.therapist_gender_pref:
            context_parts.append(f"Therapist gender: {state.therapist_gender_pref}")
        if state.city:
            context_parts.append(f"City: {state.city}")

        return "\n".join(context_parts) if context_parts else "No information collected yet."

    # FAQ trigger keywords
    FAQ_KEYWORDS = [
        "cost", "price", "pricing", "how much", "pay", "payment", "fees",
        "refund", "cancel", "cancellation", "pause", "reschedule",
        "privacy", "private", "secure", "confidential",
        "care plan", "what's included", "what is included", "what do i get",
        "session length", "how long", "format", "duration",
        "nri", "international", "outside india", "abroad",
        "neurodivergent", "adhd", "autism",
        "change therapist", "switch therapist", "different therapist",
        "who is feel your best", "what is feel your best",
        "how do i start", "how do i get started", "how does it work",
        "types of experts", "what experts",
        "severe", "psychiatric",
    ]

    def _is_faq_question(self, message: str) -> bool:
        """Check if the user's message is a FAQ-type question."""
        message_lower = message.lower()
        # Must match a keyword AND contain a question indicator
        has_keyword = any(kw in message_lower for kw in self.FAQ_KEYWORDS)
        has_question = "?" in message or any(
            q in message_lower
            for q in ["how", "what", "can i", "do you", "is it", "tell me about", "does"]
        )
        return has_keyword and has_question

    def _handle_button_action(self, state: LumiUserState, message: str) -> Optional[FlowResponse]:
        """Route CTA button selections. Returns None if not a CTA button."""
        # Don't intercept during warm-up, route selection, or consultation booking —
        # let the dedicated stage handlers process these.
        if state.stage in (
            OnboardingStage.WARMUP,
            OnboardingStage.WARMUP_2,
            OnboardingStage.ROUTE_SELECT,
            OnboardingStage.BROWSE_EXPERTS,
            OnboardingStage.CONSULTATION_INTRO,
            OnboardingStage.CONSULTATION_DATE,
            OnboardingStage.CONSULTATION_TIME_SECTION,
            OnboardingStage.CONSULTATION_TIME,
        ):
            return None

        message_lower = message.lower()

        # Continue with Lumi (no-op, fall through to normal flow)
        if message_lower in ("keep going with lumi", "let's keep going", "let's keep going"):
            return None

        # WhatsApp Community CTA
        if message_lower in ("join our safe space", "join community"):
            return FlowResponse(messages=[WHATSAPP_COMMUNITY_CTA])

        # Expert Directory CTA
        if message_lower in ("browse all experts", "browse directory", "browse experts"):
            return FlowResponse(messages=[
                EXPERT_DIRECTORY_CTA,
                "Take your time browsing! I'm still here if you'd like to continue or have questions.",
            ])

        # Browse all experts keyword detection
        if any(kw in message_lower for kw in [
            "all experts", "all therapists", "browse experts",
            "list of therapists", "expert directory", "see everyone",
        ]):
            return FlowResponse(messages=[
                EXPERT_DIRECTORY_CTA,
                "Take your time browsing! I'm still here if you'd like to continue or have questions.",
            ])

        # Book a call / Talk to team -> consultation booking flow
        if message_lower in ("book a call", "talk to care team"):
            state.selected_route = "consultation"
            state.stage = OnboardingStage.CONSULTATION_INTRO
            return FlowResponse(
                messages=[
                    "Absolutely! I'd love to connect you with one of our Care Specialists.",
                    "Could you let me know which days generally work best for you?",
                ],
            )

        return None

    async def _process_stage(
        self,
        state: LumiUserState,
        message: str,
        is_button: bool,
    ) -> FlowResponse:
        """Process message based on current stage."""
        stage = state.stage
        logger.info(f"[LUMI_FLOW] Processing stage {stage} for {state.phone_number}")

        # Check if user is asking a FAQ question - answer without advancing stage
        if self._is_faq_question(message):
            try:
                faq_response = await self._generate_llm_response(state, message)
                return FlowResponse(
                    messages=[faq_response],
                    buttons=self._get_stage_buttons(stage),
                    list_options=self._get_stage_list_options(stage),
                )
            except Exception as e:
                logger.warning(f"[LUMI_FLOW] FAQ response failed, continuing with normal flow: {e}")

        # Handle welcome reply — ask how they're doing (warm-up turn 1)
        if stage == OnboardingStage.WELCOME:
            try:
                response_text = await self._generate_llm_response(state, message)
            except Exception:
                response_text = "That's great to hear! So tell me, how have you been feeling lately?"
            state.stage = OnboardingStage.WARMUP
            return FlowResponse(messages=[response_text])

        # Handle warm-up turn 1 reply — ask a deeper follow-up (warm-up turn 2)
        if stage == OnboardingStage.WARMUP:
            try:
                response_text = await self._generate_llm_response(state, message)
            except Exception:
                response_text = "I appreciate you sharing that. Can you tell me a bit more about what's been going on?"
            state.stage = OnboardingStage.WARMUP_2
            return FlowResponse(messages=[response_text])

        # Handle warm-up turn 2 reply — acknowledge and show route options
        if stage == OnboardingStage.WARMUP_2:
            try:
                response_text = await self._generate_llm_response(state, message)
            except Exception:
                response_text = "Thank you for sharing that with me. Let me show you how I can help."
            state.stage = OnboardingStage.ROUTE_SELECT
            return FlowResponse(
                messages=[response_text],
                buttons=[
                    {"id": "browse_experts", "title": "Browse all experts"},
                    {"id": "talk_specialist", "title": "Talk to Care team"},
                    {"id": "continue_lumi", "title": "Continue with Lumi"},
                ],
            )

        # Handle browse experts — answer questions, then auto-close after 5 messages
        if stage == OnboardingStage.BROWSE_EXPERTS:
            state.browse_messages_remaining = max(0, (state.browse_messages_remaining or 5) - 1)
            try:
                response_text = await self._generate_llm_response(state, message)
            except Exception as e:
                logger.error(f"[LUMI_FLOW] BROWSE_EXPERTS LLM error: {e}")
                response_text = (
                    "That's a great question! I'm having a small technical hiccup right now, "
                    "but our Care team can give you all the details. "
                    "Would you like me to connect you with them?"
                )
            if state.browse_messages_remaining <= 0:
                state.stage = OnboardingStage.ARCHIVED
                return FlowResponse(messages=[
                    response_text,
                    "It was great chatting with you! If you ever want to come back and get matched with a therapist, just send us a message. Take care!",
                ])
            return FlowResponse(messages=[response_text])

        # Handle consultation intro — acknowledge, then show date picker
        if stage == OnboardingStage.CONSULTATION_INTRO:
            try:
                response_text = await self._generate_llm_response(state, message)
            except Exception:
                response_text = "Let me check what's available for you."
            state.stage = OnboardingStage.CONSULTATION_DATE
            dates = get_upcoming_dates(3)
            buttons = [{"id": d["date"], "title": d["label"][:20]} for d in dates]
            return FlowResponse(
                messages=[response_text],
                buttons=buttons,
            )

        # Handle route selection and consultation booking stages
        if stage == OnboardingStage.ROUTE_SELECT:
            return await self._handle_route_select(state, message)
        if stage == OnboardingStage.CONSULTATION_DATE:
            return await self._handle_consultation_date(state, message)
        if stage == OnboardingStage.CONSULTATION_TIME_SECTION:
            return await self._handle_consultation_time_section(state, message)
        if stage == OnboardingStage.CONSULTATION_TIME:
            return await self._handle_consultation_time(state, message)

        # Handle post-matching stages based on CURRENT stage (not next stage)
        # These stages are not in the linear stage_order and handle their own transitions
        if stage == OnboardingStage.MATCH_REVEAL:
            return await self._handle_match_reveal(state, message)
        elif stage == OnboardingStage.ALTERNATIVE_THERAPISTS:
            return self._handle_alternative_therapists(state, message)
        elif stage == OnboardingStage.BOOKING:
            return self._handle_booking(state, message)

        # Extract data from message based on stage
        self._extract_stage_data(state, message, stage)

        # Therapy History: send fixed follow-up template based on answer
        if stage == OnboardingStage.THERAPY_HISTORY and state.therapy_history:
            followup = THERAPY_HISTORY_FOLLOWUPS.get(state.therapy_history)
            if followup:
                if state.therapy_history == "new":
                    # "New" follow-up asks a question, stay on THERAPY_HISTORY
                    # Mark as sent so we don't repeat it on the user's next reply
                    state.therapy_history = "new_followup_sent"
                    return FlowResponse(messages=[followup])
                elif state.therapy_history != "new_followup_sent":
                    # "didnt_stick" and "helped" are statements, advance to next stage
                    state.stage = OnboardingStage.CARE_PREFERENCES
                    return FlowResponse(
                        messages=[followup],
                        buttons=self._get_stage_buttons(OnboardingStage.CARE_PREFERENCES),
                        list_options=self._get_stage_list_options(OnboardingStage.CARE_PREFERENCES),
                    )

        # Medication "Yes": send fixed follow-up asking for medication details
        if (stage == OnboardingStage.MEDICATION
                and state.on_medication
                and not state.medications):
            return FlowResponse(messages=[MEDICATION_YES_FOLLOWUP])

        # Determine next stage
        next_stage = self._get_next_stage(stage, state, message)

        # Handle processing (therapist matching) - legacy path
        if next_stage == OnboardingStage.PROCESSING:
            return await self._handle_processing(state, message)

        # Handle preferences collected terminal (Lumi flow end)
        if next_stage == OnboardingStage.PREFERENCES_COLLECTED:
            state.stage = OnboardingStage.PREFERENCES_COLLECTED
            return FlowResponse(
                messages=[STAGE_MESSAGES[OnboardingStage.PREFERENCES_COLLECTED]],
            )

        # Move to next stage and generate response
        state.stage = next_stage

        try:
            response_text = await self._generate_llm_response(state, message)
            return FlowResponse(
                messages=[response_text],
                buttons=self._get_stage_buttons(next_stage),
                list_options=self._get_stage_list_options(next_stage),
            )
        except Exception as e:
            logger.error(f"[LUMI_FLOW] LLM error, using fallback: {e}")
            # Fallback to template
            template = STAGE_MESSAGES.get(next_stage, "Let me help you with that.")
            return FlowResponse(
                messages=[template],
                buttons=self._get_stage_buttons(next_stage),
                list_options=self._get_stage_list_options(next_stage),
            )

    def _extract_stage_data(self, state: LumiUserState, message: str, stage: OnboardingStage):
        """Extract and store data from user message based on current stage."""
        message_lower = message.lower()

        if stage == OnboardingStage.DEMOGRAPHICS:
            # Extract age
            age_match = re.search(r"\b(\d{1,2})\b", message)
            if age_match:
                state.age = int(age_match.group(1))
            # Extract gender
            if any(g in message_lower for g in ["female", "woman", "girl"]):
                state.gender = "woman"
            elif any(g in message_lower for g in ["male", "man", "boy"]):
                state.gender = "man"
            elif any(g in message_lower for g in ["non-binary", "nonbinary", "they"]):
                state.gender = "non-binary"
                state.queer_affirming_flag = True

        elif stage == OnboardingStage.STORY:
            state.story_text = message
            # Detect concerns
            for concern, keywords in self.CONCERN_KEYWORDS.items():
                if any(kw in message_lower for kw in keywords):
                    if concern not in state.concerns:
                        state.concerns.append(concern)
                    if concern == "trauma":
                        state.trauma_flag = True

        elif stage == OnboardingStage.THERAPY_HISTORY:
            # Don't overwrite if follow-up was already sent (user is responding to it)
            if not state.therapy_history or state.therapy_history not in ("new_followup_sent", "didnt_stick", "helped"):
                if "didn't" in message_lower or "didnt" in message_lower:
                    state.therapy_history = "didnt_stick"
                elif "helped" in message_lower:
                    state.therapy_history = "helped"
                else:
                    state.therapy_history = "new"

        elif stage == OnboardingStage.CARE_PREFERENCES:
            if "full" in message_lower:
                state.care_preference = "full_care"
            elif "just therapy" in message_lower or "therapy" in message_lower:
                state.care_preference = "just_therapy"
            else:
                state.care_preference = "not_sure"

        elif stage == OnboardingStage.MEDICATION:
            if "yes" in message_lower:
                state.on_medication = True
            elif "no" in message_lower:
                state.on_medication = False
            elif state.on_medication:
                state.medications = message

        elif stage == OnboardingStage.LANGUAGE:
            languages = [
                "hindi", "english", "tamil", "telugu", "bengali",
                "marathi", "gujarati", "kannada", "malayalam", "punjabi",
            ]
            for lang in languages:
                if lang in message_lower:
                    state.language = lang.capitalize()
                    break
            if not state.language:
                state.language = message.strip().capitalize()

        elif stage == OnboardingStage.THERAPIST_STYLE:
            style_map = {
                "warm": "Warm & nurturing",
                "structured": "Structured & direct",
                "queer": "Queer-affirming",
                "trauma": "Trauma-informed",
                "cultural": "Culturally aware",
                "holistic": "Holistic",
                "solution": "Solution-focused",
                "not sure": "Not sure",
            }
            for key, value in style_map.items():
                if key in message_lower and value not in state.therapist_style:
                    state.therapist_style.append(value)

        elif stage == OnboardingStage.GENDER_PREFERENCE:
            if "man" in message_lower or "male" in message_lower:
                state.therapist_gender_pref = "man"
            elif "woman" in message_lower or "female" in message_lower:
                state.therapist_gender_pref = "woman"
            else:
                state.therapist_gender_pref = "flexible"

        elif stage == OnboardingStage.PERSONAL_CONTEXT:
            statuses = ["single", "married", "relationship", "divorced", "separated", "widowed", "prefer not"]
            for s in statuses:
                if s in message_lower:
                    if s in ("divorced", "separated"):
                        state.relationship_status = "separated_divorced"
                    elif "prefer" in s:
                        state.relationship_status = "prefer_not_say"
                    else:
                        state.relationship_status = s
                    break

        elif stage == OnboardingStage.PERSONAL_CITY:
            state.city = message.strip()

    def _get_next_stage(self, current: OnboardingStage, state: LumiUserState, message: str) -> OnboardingStage:
        """Determine the next stage based on current stage and user input."""
        stage_order = [
            OnboardingStage.WELCOME,
            OnboardingStage.ROUTE_SELECT,
            OnboardingStage.DEMOGRAPHICS,
            OnboardingStage.STORY,
            OnboardingStage.THERAPY_HISTORY,
            OnboardingStage.CARE_PREFERENCES,
            OnboardingStage.MEDICATION,
            OnboardingStage.CONCERNS,
            OnboardingStage.LANGUAGE,
            OnboardingStage.THERAPIST_STYLE,
            OnboardingStage.GENDER_PREFERENCE,
            OnboardingStage.PERSONAL_CONTEXT,
            OnboardingStage.PERSONAL_CITY,
            OnboardingStage.PREFERENCES_COLLECTED,
        ]

        # Special case: medication yes needs followup
        if current == OnboardingStage.MEDICATION and "yes" in message.lower() and not state.medications:
            return OnboardingStage.MEDICATION  # Stay for followup

        try:
            idx = stage_order.index(current)
            if idx < len(stage_order) - 1:
                return stage_order[idx + 1]
        except ValueError:
            pass

        return OnboardingStage.PREFERENCES_COLLECTED

    def _get_stage_buttons(self, stage: OnboardingStage) -> Optional[List[dict]]:
        """Get appropriate buttons for a stage (max 3, for WhatsApp reply buttons)."""
        buttons_map = {
            OnboardingStage.ROUTE_SELECT: [
                {"id": "browse_experts", "title": "Browse all experts"},
                {"id": "talk_specialist", "title": "Talk to Care team"},
                {"id": "continue_lumi", "title": "Continue with Lumi"},
            ],
            OnboardingStage.DEMOGRAPHICS: None,  # Free text
            OnboardingStage.STORY: None,  # Free text
            OnboardingStage.THERAPY_HISTORY: [
                {"id": "didnt_stick", "title": "Yes, didn't stick"},
                {"id": "helped", "title": "Yes, it helped"},
                {"id": "new", "title": "No, I'm new"},
            ],
            OnboardingStage.CARE_PREFERENCES: [
                {"id": "full_care", "title": "Full care plan"},
                {"id": "just_therapy", "title": "Just therapy"},
                {"id": "not_sure", "title": "Not sure yet"},
            ],
            OnboardingStage.MEDICATION: [
                {"id": "yes", "title": "Yes"},
                {"id": "no", "title": "No"},
            ],
            # Language and Personal Context use list messages (see _get_stage_list_options)
            OnboardingStage.GENDER_PREFERENCE: [
                {"id": "man", "title": "Man"},
                {"id": "woman", "title": "Woman"},
                {"id": "flexible", "title": "I'm flexible"},
            ],
        }
        return buttons_map.get(stage)

    def _get_stage_list_options(self, stage: OnboardingStage) -> Optional[dict]:
        """Get list message options for stages with >3 choices."""
        list_map = {
            OnboardingStage.LANGUAGE: {
                "button_text": "Choose language",
                "sections": [{
                    "title": "Languages",
                    "rows": [
                        {"id": "hindi", "title": "Hindi"},
                        {"id": "english", "title": "English"},
                        {"id": "tamil", "title": "Tamil"},
                        {"id": "telugu", "title": "Telugu"},
                        {"id": "bengali", "title": "Bengali"},
                        {"id": "marathi", "title": "Marathi"},
                        {"id": "gujarati", "title": "Gujarati"},
                        {"id": "kannada", "title": "Kannada"},
                        {"id": "malayalam", "title": "Malayalam"},
                        {"id": "punjabi", "title": "Punjabi"},
                    ],
                }],
            },
            OnboardingStage.THERAPIST_STYLE: {
                "button_text": "Choose style",
                "sections": [{
                    "title": "Therapist Style",
                    "rows": [
                        {"id": "warm", "title": "Warm & nurturing"},
                        {"id": "structured", "title": "Structured & direct"},
                        {"id": "queer", "title": "Queer-affirming"},
                        {"id": "trauma", "title": "Trauma-informed"},
                        {"id": "cultural", "title": "Culturally aware"},
                        {"id": "holistic", "title": "Holistic"},
                        {"id": "solution", "title": "Solution-focused"},
                        {"id": "not_sure", "title": "I'm not sure"},
                    ],
                }],
            },
            OnboardingStage.PERSONAL_CONTEXT: {
                "button_text": "Choose status",
                "sections": [{
                    "title": "Relationship Status",
                    "rows": [
                        {"id": "single", "title": "Single"},
                        {"id": "married", "title": "Married"},
                        {"id": "relationship", "title": "In a relationship"},
                        {"id": "divorced", "title": "Separated/Divorced"},
                        {"id": "widowed", "title": "Widowed"},
                        {"id": "prefer_not_say", "title": "Prefer not to say"},
                    ],
                }],
            },
        }
        return list_map.get(stage)

    async def _handle_route_select(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle the route selection after welcome."""
        message_lower = message.lower()

        # Option 1: Browse experts
        if any(kw in message_lower for kw in ["browse", "experts", "directory"]):
            state.selected_route = "browse_experts"
            state.stage = OnboardingStage.BROWSE_EXPERTS
            state.browse_messages_remaining = 5
            return FlowResponse(
                messages=[
                    EXPERT_DIRECTORY_CTA,
                    "Take your time exploring! I'm still here if you have any questions about our experts, pricing, or how therapy works.",
                ],
            )

        # Option 2: Talk to Care Specialist
        if any(kw in message_lower for kw in ["talk", "specialist", "care team", "call"]):
            state.selected_route = "consultation"
            state.stage = OnboardingStage.CONSULTATION_INTRO
            return FlowResponse(
                messages=[
                    "Absolutely! I'd love to connect you with one of our Care Specialists. They're great at helping you figure out the right path forward.",
                    "Before I check available slots, could you let me know which days generally work best for you?",
                ],
            )

        # Option 3: Continue with Lumi (default)
        state.selected_route = "lumi_flow"
        state.stage = OnboardingStage.DEMOGRAPHICS

        try:
            response_text = await self._generate_llm_response(state, message)
            return FlowResponse(messages=[response_text])
        except Exception:
            return FlowResponse(
                messages=[STAGE_MESSAGES[OnboardingStage.DEMOGRAPHICS]]
            )

    async def _handle_consultation_date(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle date selection for consultation booking."""
        message_stripped = message.strip()
        selected_date = None

        # Try to parse date from button ID (YYYY-MM-DD)
        try:
            selected_date = date_cls.fromisoformat(message_stripped)
        except ValueError:
            pass

        # Try natural text like "Today", "Tomorrow"
        if not selected_date:
            message_lower = message_stripped.lower()
            if "today" in message_lower:
                selected_date = date_cls.today()
            elif "tomorrow" in message_lower:
                selected_date = date_cls.today() + timedelta(days=1)
            else:
                # Try to match label text from buttons
                dates = get_upcoming_dates(3)
                for d in dates:
                    if d["label"].lower() in message_lower or message_lower in d["label"].lower():
                        selected_date = date_cls.fromisoformat(d["date"])
                        break

        if not selected_date:
            dates = get_upcoming_dates(3)
            buttons = [{"id": d["date"], "title": d["label"][:20]} for d in dates]
            return FlowResponse(
                messages=["I didn't catch that. Could you pick one of these dates?"],
                buttons=buttons,
            )

        # Store selected date
        state.consultation_date = selected_date.isoformat()

        # Fetch available slots
        consultation_client = get_consultation_client()
        if not consultation_client:
            # API not configured - fallback to human handoff
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = "consultation_api_unavailable"
            return FlowResponse(
                messages=[
                    HUMAN_HANDOFF_MESSAGE,
                    "I'm handing you over to our Care team now. If you need me again, just send a message anytime!",
                ],
                is_handoff=True,
                handoff_reason="consultation_api_unavailable",
            )

        booked_events = await consultation_client.get_booked_slots(state.consultation_date)
        available_slots = consultation_client.calculate_available_slots(booked_events, selected_date)

        if not available_slots:
            dates = get_upcoming_dates(3)
            buttons = [{"id": d["date"], "title": d["label"][:20]} for d in dates]
            date_label = selected_date.strftime("%A, %d %b")
            return FlowResponse(
                messages=[f"Unfortunately, there are no slots available on {date_label}. Could you try another date?"],
                buttons=buttons,
            )

        # Move to time section selection (Morning / Afternoon / Evening)
        state.stage = OnboardingStage.CONSULTATION_TIME_SECTION
        state.available_slots = available_slots  # Store for next step

        morning = [s for s in available_slots if int(s[:2]) < 12]
        afternoon = [s for s in available_slots if 12 <= int(s[:2]) < 17]
        evening = [s for s in available_slots if int(s[:2]) >= 17]

        section_buttons = []
        if morning:
            section_buttons.append({"id": "section_morning", "title": "Morning"})
        if afternoon:
            section_buttons.append({"id": "section_afternoon", "title": "Afternoon"})
        if evening:
            section_buttons.append({"id": "section_evening", "title": "Evening"})

        date_label = selected_date.strftime("%A, %d %b")
        return FlowResponse(
            messages=[f"Great! What time of day works best for you on {date_label}?"],
            buttons=section_buttons,
        )

    async def _handle_consultation_time_section(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle day-section selection (Morning/Afternoon/Evening), then show up to 3 time slots."""
        msg_lower = message.strip().lower()
        available = state.available_slots or []

        slots = None
        if "morning" in msg_lower:
            slots = [s for s in available if int(s[:2]) < 12]
        elif "afternoon" in msg_lower:
            slots = [s for s in available if 12 <= int(s[:2]) < 17]
        elif "evening" in msg_lower:
            slots = [s for s in available if int(s[:2]) >= 17]

        if slots is None:
            # Didn't understand — re-show section buttons
            morning = [s for s in available if int(s[:2]) < 12]
            afternoon = [s for s in available if 12 <= int(s[:2]) < 17]
            evening = [s for s in available if int(s[:2]) >= 17]
            section_buttons = []
            if morning:
                section_buttons.append({"id": "section_morning", "title": "Morning"})
            if afternoon:
                section_buttons.append({"id": "section_afternoon", "title": "Afternoon"})
            if evening:
                section_buttons.append({"id": "section_evening", "title": "Evening"})
            return FlowResponse(
                messages=["Could you pick a time of day? Morning, Afternoon, or Evening?"],
                buttons=section_buttons,
            )

        if not slots:
            # Section exists but no slots available — re-show section buttons
            morning = [s for s in available if int(s[:2]) < 12]
            afternoon = [s for s in available if 12 <= int(s[:2]) < 17]
            evening = [s for s in available if int(s[:2]) >= 17]
            section_buttons = []
            if morning:
                section_buttons.append({"id": "section_morning", "title": "Morning"})
            if afternoon:
                section_buttons.append({"id": "section_afternoon", "title": "Afternoon"})
            if evening:
                section_buttons.append({"id": "section_evening", "title": "Evening"})
            return FlowResponse(
                messages=["No slots available in that window. Could you try another time of day?"],
                buttons=section_buttons,
            )

        # Show up to 3 slots as buttons
        state.stage = OnboardingStage.CONSULTATION_TIME
        display_slots = slots[:3]
        buttons = [{"id": s, "title": format_time_label(s)} for s in display_slots]

        return FlowResponse(
            messages=["Here are some times. Pick one that works for you!"],
            buttons=buttons,
        )

    async def _handle_consultation_time(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle time slot selection and book the consultation."""
        message_stripped = message.strip()
        selected_time = None

        # Try HH:MM format (from list reply ID)
        time_match = re.match(r"^(\d{1,2}):(\d{2})$", message_stripped)
        if time_match:
            selected_time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"

        # Try "9:00 AM" style from list reply title
        if not selected_time:
            am_pm_match = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", message_stripped, re.IGNORECASE)
            if am_pm_match:
                hour = int(am_pm_match.group(1))
                minute = am_pm_match.group(2)
                period = am_pm_match.group(3).upper()
                if period == "PM" and hour != 12:
                    hour += 12
                elif period == "AM" and hour == 12:
                    hour = 0
                selected_time = f"{hour:02d}:{minute}"

        # Try natural formats: "12pm", "2pm", "2:30pm", "230pm"
        if not selected_time:
            natural_match = re.match(
                r"^(\d{1,2})(?::?(\d{2}))?\s*(am|pm)$",
                message_stripped,
                re.IGNORECASE,
            )
            if natural_match:
                hour = int(natural_match.group(1))
                minute = natural_match.group(2) or "00"
                period = natural_match.group(3).upper()
                if period == "PM" and hour != 12:
                    hour += 12
                elif period == "AM" and hour == 12:
                    hour = 0
                selected_time = f"{hour:02d}:{minute}"

        # If user sent a date label while we expected a time, go back to date selection
        if not selected_time:
            msg_lower = message_stripped.lower()
            date_keywords = ["today", "tomorrow", "mon", "tue", "wed", "thu", "fri", "sat"]
            if any(kw in msg_lower for kw in date_keywords):
                state.stage = OnboardingStage.CONSULTATION_DATE
                dates = get_upcoming_dates(3)
                buttons = [{"id": d["date"], "title": d["label"][:20]} for d in dates]
                return FlowResponse(
                    messages=["Looks like you picked a date. Let's choose a date first, then we'll pick a time."],
                    buttons=buttons,
                )

        # On genuine parse failure, re-show time slot buttons
        if not selected_time:
            available = state.available_slots or []
            if available:
                display = available[:3]
                buttons = [{"id": s, "title": format_time_label(s)} for s in display]
                return FlowResponse(
                    messages=["I didn't quite catch that. Could you pick one of these times?"],
                    buttons=buttons,
                )
            return FlowResponse(
                messages=["I didn't catch that. Could you type a time like '10:00 AM' or '2pm'?"],
            )

        # Store selected time and attempt booking
        state.consultation_time = selected_time

        consultation_client = get_consultation_client()
        if not consultation_client:
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = "consultation_api_unavailable"
            return FlowResponse(
                messages=[
                    HUMAN_HANDOFF_MESSAGE,
                    "I'm handing you over to our Care team now. If you need me again, just send a message anytime!",
                ],
                is_handoff=True,
                handoff_reason="consultation_api_unavailable",
            )

        # Format phone for E.164
        phone = f"+{state.phone_number}" if not state.phone_number.startswith("+") else state.phone_number

        try:
            result = await consultation_client.book_slot(
                phone=phone,
                name=state.phone_number,  # Name not collected yet at this point
                meeting_date=state.consultation_date,
                meeting_time=state.consultation_time,
            )

            if result["status_code"] in (200, 201):
                state.stage = OnboardingStage.CONSULTATION_CONFIRMED

                booked_date = date_cls.fromisoformat(state.consultation_date)
                date_label = booked_date.strftime("%A, %d %B")
                time_label = format_time_label(state.consultation_time)

                confirmation_msg = (
                    f"Your consultation is booked!\n\n"
                    f"Date: {date_label}\n"
                    f"Time: {time_label}\n\n"
                    f"Our Care Specialist will call you at this number. "
                    f"If you need to reschedule, just send us a message.\n\n"
                    f"Looking forward to connecting you with the right support!"
                )
                return FlowResponse(messages=[confirmation_msg])
            elif result["status_code"] == 409:
                # Slot already booked - ask for another time
                return FlowResponse(
                    messages=["That slot just got booked by someone else! Could you pick another time?"],
                )
            else:
                logger.error(f"[CONSULTATION] Booking failed: {result}")
                return FlowResponse(
                    messages=["I'm having a little trouble booking that slot. Could you try another time?"],
                )

        except Exception as e:
            logger.error(f"[CONSULTATION] Booking exception: {e}")
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = "consultation_booking_error"
            return FlowResponse(
                messages=[
                    "I ran into an issue booking your consultation. Let me connect you with our Care team directly.",
                    HUMAN_HANDOFF_MESSAGE,
                ],
                is_handoff=True,
                handoff_reason="consultation_booking_error",
            )

    async def _handle_processing(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle the processing/matching stage."""
        state.stage = OnboardingStage.PROCESSING

        # Run matching
        therapist = match_therapist(state)
        state.matched_therapist_id = therapist.id

        # Generate match card
        match_card = format_therapist_card(therapist, state)

        state.stage = OnboardingStage.MATCH_REVEAL

        return FlowResponse(
            messages=["Perfect. Give me just a moment... ✨", match_card],
            buttons=[
                {"id": "book_session", "title": "Yes, let's book"},
                {"id": "show_options", "title": "Show other options"},
            ],
        )

    async def _handle_match_reveal(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle response to therapist match."""
        message_lower = message.lower()

        if "book" in message_lower or "yes" in message_lower:
            state.stage = OnboardingStage.BOOKING
            return FlowResponse(
                messages=[STAGE_MESSAGES[OnboardingStage.BOOKING]],
                buttons=[{"id": "confirm", "title": "I confirm"}],
            )
        else:
            state.therapist_options_shown_count += 1

            if state.therapist_options_shown_count >= 2:
                return FlowResponse(
                    messages=[FRICTION_CYCLING_OPTIONS + "\n\n" + EXPERT_DIRECTORY_CTA],
                    buttons=[
                        {"id": "talk_to_team", "title": "Talk to Care team"},
                        {"id": "browse_directory", "title": "Browse all experts"},
                        {"id": "show_more", "title": "Show me more"},
                    ],
                )

            alternatives = get_alternative_therapists(state, exclude_id=state.matched_therapist_id, count=2)
            state.alternative_therapist_ids = [t.id for t in alternatives]
            alt_cards = "\n\n---\n\n".join([format_alternative_card(t) for t in alternatives])

            state.stage = OnboardingStage.ALTERNATIVE_THERAPISTS
            return FlowResponse(
                messages=[f"No problem! Here are two other therapists:\n\n{alt_cards}"],
                buttons=[
                    {"id": "book_session", "title": "Book a session"},
                    {"id": "browse_directory", "title": "Browse all experts"},
                    {"id": "talk_to_team", "title": "Talk to Care team"},
                ],
            )

    def _handle_alternative_therapists(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle alternative therapist selection."""
        message_lower = message.lower()

        if "care team" in message_lower or "talk to" in message_lower:
            state.selected_route = "consultation"
            state.stage = OnboardingStage.CONSULTATION_INTRO
            return FlowResponse(
                messages=[
                    "Absolutely! I'd love to connect you with one of our Care Specialists.",
                    "Could you let me know which days generally work best for you?",
                ],
            )

        if "browse" in message_lower or "directory" in message_lower or "all experts" in message_lower:
            return FlowResponse(messages=[
                EXPERT_DIRECTORY_CTA,
                "Take your time browsing! I'm still here if you'd like to continue or have questions.",
            ])

        state.stage = OnboardingStage.BOOKING
        return FlowResponse(
            messages=[STAGE_MESSAGES[OnboardingStage.BOOKING]],
            buttons=[{"id": "confirm", "title": "I confirm"}],
        )

    def _handle_booking(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle booking confirmation."""
        message_lower = message.lower()

        if "confirm" in message_lower or "yes" in message_lower:
            state.consent_acknowledged = True
            state.stage = OnboardingStage.CONFIRMED

            return FlowResponse(messages=[
                "Your preferences have been saved! Our Care Specialist will assist you shortly with the booking. We're excited to support your journey."
            ])

        return FlowResponse(
            messages=["Please confirm to proceed with your booking."],
            buttons=[{"id": "confirm", "title": "I confirm"}],
        )

# Module-level handler instance
_handler: Optional[LumiFlowHandler] = None


def get_flow_handler() -> LumiFlowHandler:
    """Get or create the flow handler instance."""
    global _handler
    if _handler is None:
        _handler = LumiFlowHandler()
    return _handler

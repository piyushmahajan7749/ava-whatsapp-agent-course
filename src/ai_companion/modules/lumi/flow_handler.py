"""
Lumi onboarding flow handler.

Manages stage transitions, processes user input, and generates responses
for the 15-stage onboarding flow using LLM for natural conversations.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
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
    FRICTION_CHECKPOINT,
    FRICTION_CYCLING_OPTIONS,
    HUMAN_HANDOFF_MESSAGE,
    CRISIS_RESPONSE,
)
from ai_companion.modules.lumi.crisis_detector import check_for_crisis
from ai_companion.modules.lumi.friction_detector import check_for_friction
from ai_companion.modules.lumi.matching import (
    match_therapist,
    get_alternative_therapists,
    format_therapist_card,
    format_alternative_card,
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
    OnboardingStage.WELCOME: """The user just started. Send a warm welcome as Lumi. Introduce yourself, explain you'll help find the right therapist, and assure them everything is confidential. Ask if they're ready to begin.""",

    OnboardingStage.DEMOGRAPHICS: """Ask about their age and gender identity in a friendly, casual way. Keep it brief - just one or two questions.""",

    OnboardingStage.STORY: """Ask what brings them here today. Be warm and open. Let them know they can type or send a voice note - whatever feels easier.""",

    OnboardingStage.THERAPY_HISTORY: """Ask if they've tried therapy before. Be curious but non-judgmental. Acknowledge their experience appropriately.""",

    OnboardingStage.CARE_PREFERENCES: """Ask what kind of support feels right - full care plan (therapy + lifestyle), just therapy, or not sure yet. Explain briefly what each means.""",

    OnboardingStage.MEDICATION: """Ask if they're currently taking any mental health medications. Be gentle and reassure this is just to help with matching.""",

    OnboardingStage.CONCERNS: """Ask what they're hoping to work on. List some options like anxiety, depression, relationships, etc. Let them select multiple.""",

    OnboardingStage.LANGUAGE: """Ask their preferred language for therapy. Mention options like Hindi, English, Tamil, etc.""",

    OnboardingStage.THERAPIST_STYLE: """Ask about their preferred therapist style - warm & nurturing, structured & direct, trauma-informed, queer-affirming, etc.""",

    OnboardingStage.GENDER_PREFERENCE: """Ask if they have a preference for their therapist's gender - man, woman, or flexible.""",

    OnboardingStage.PERSONAL_CONTEXT: """Ask about their relationship status. Keep it casual and include a 'prefer not to say' option.""",

    OnboardingStage.PERSONAL_DOB: """Ask for their date of birth in DD/MM/YYYY format. Explain it helps with records.""",

    OnboardingStage.PERSONAL_CITY: """Ask which city they're based in.""",

    OnboardingStage.PROCESSING: """Let them know you're finding the right match. Build some anticipation.""",

    OnboardingStage.MATCH_REVEAL: """Present the matched therapist enthusiastically. Include their name, bio, and why they're a good match. Ask if they want to book or see other options.""",

    OnboardingStage.BOOKING: """Ask them to confirm they understand this isn't a diagnosis and that the team may contact them. Get their confirmation to proceed.""",

    OnboardingStage.CONFIRMED: """Celebrate! Confirm the booking, share next steps, and let them know the care team will reach out.""",
}


@dataclass
class FlowResponse:
    """Response from flow handler."""

    messages: List[str]
    buttons: Optional[List[dict]] = None
    is_handoff: bool = False
    handoff_reason: Optional[str] = None
    is_crisis: bool = False
    new_state: Optional[LumiUserState] = None


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

        # Check for handoff keywords
        handoff_decision = should_handoff(message_text)
        if handoff_decision.should_handoff:
            logger.info(f"[LUMI_FLOW] Handoff triggered: {handoff_decision.reason}")
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = handoff_decision.reason
            save_user_state(state)
            return FlowResponse(
                messages=[HUMAN_HANDOFF_MESSAGE.format(care_specialist_name="our Care Specialist")],
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

        # Process based on current stage
        response = await self._process_stage(state, message_text, is_button_response)

        # Check if we should offer handoff due to friction
        if friction_decision.should_offer_handoff and not response.is_handoff:
            response.messages.append(FRICTION_CHECKPOINT)
            response.buttons = [
                {"id": "continue_lumi", "title": "Keep going with Lumi"},
                {"id": "talk_to_team", "title": "Talk to someone"},
            ]

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
        """Generate welcome message for new users."""
        state.stage = OnboardingStage.WELCOME

        # Add user's initial message to history
        state.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })

        # Generate welcome with LLM
        try:
            response = await self._generate_llm_response(state, user_message)

            # Add to history
            state.conversation_history.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            })

            # Move to demographics after welcome
            state.stage = OnboardingStage.DEMOGRAPHICS

            return FlowResponse(
                messages=[response],
                buttons=[
                    {"id": "sounds_good", "title": "Sounds good!"},
                    {"id": "tell_me_more", "title": "Tell me more"},
                ],
            )
        except Exception as e:
            logger.error(f"[LUMI_FLOW] LLM error: {e}")
            # Fallback to template
            state.stage = OnboardingStage.DEMOGRAPHICS
            return FlowResponse(
                messages=[STAGE_MESSAGES[OnboardingStage.WELCOME]],
                buttons=[
                    {"id": "sounds_good", "title": "Sounds good!"},
                    {"id": "tell_me_more", "title": "Tell me more"},
                ],
            )

    async def _generate_llm_response(self, state: LumiUserState, user_message: str) -> str:
        """Generate a response using the LLM with conversation context."""

        # Build system prompt with persona and stage guidance
        stage = state.stage
        stage_guidance = STAGE_GUIDANCE.get(stage, "Continue the conversation naturally.")

        # Include user context in system prompt
        user_context = self._build_user_context(state)

        system_prompt = f"""{LUMI_PERSONA}

Current stage: {stage.value}
Stage guidance: {stage_guidance}

User context:
{user_context}

IMPORTANT RULES:
- Keep responses SHORT (2-3 sentences max)
- Be warm but concise
- One question at a time
- Use emojis sparingly (1-2 max)
- Never diagnose or give medical advice
- Respond naturally to what the user said
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
            return response.content.strip()
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

    async def _process_stage(
        self,
        state: LumiUserState,
        message: str,
        is_button: bool,
    ) -> FlowResponse:
        """Process message based on current stage."""
        stage = state.stage
        logger.info(f"[LUMI_FLOW] Processing stage {stage} for {state.phone_number}")

        # Extract data from message based on stage
        self._extract_stage_data(state, message, stage)

        # Determine next stage
        next_stage = self._get_next_stage(stage, state, message)

        # Special handling for certain stages
        if next_stage == OnboardingStage.PROCESSING:
            return await self._handle_processing(state, message)
        elif next_stage == OnboardingStage.MATCH_REVEAL:
            return await self._handle_match_reveal(state, message)
        elif next_stage == OnboardingStage.ALTERNATIVE_THERAPISTS:
            return self._handle_alternative_therapists(state, message)
        elif next_stage == OnboardingStage.BOOKING:
            return self._handle_booking(state, message)
        elif next_stage == OnboardingStage.CONFIRMED:
            return self._handle_confirmed(state, message)

        # Move to next stage and generate response
        state.stage = next_stage

        try:
            response_text = await self._generate_llm_response(state, message)
            return FlowResponse(
                messages=[response_text],
                buttons=self._get_stage_buttons(next_stage),
            )
        except Exception as e:
            logger.error(f"[LUMI_FLOW] LLM error, using fallback: {e}")
            # Fallback to template
            template = STAGE_MESSAGES.get(next_stage, "Let me help you with that.")
            return FlowResponse(
                messages=[template],
                buttons=self._get_stage_buttons(next_stage),
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
            languages = ["hindi", "english", "tamil", "telugu", "bengali", "marathi"]
            for lang in languages:
                if lang in message_lower:
                    state.language = lang.capitalize()
                    break
            if not state.language:
                state.language = message.strip().capitalize()

        elif stage == OnboardingStage.THERAPIST_STYLE:
            styles = {"warm": "Warm & nurturing", "structured": "Structured & direct",
                     "queer": "Queer-affirming", "trauma": "Trauma-informed"}
            for key, value in styles.items():
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
            statuses = ["single", "married", "relationship", "divorced"]
            for s in statuses:
                if s in message_lower:
                    state.relationship_status = s
                    break

        elif stage == OnboardingStage.PERSONAL_DOB:
            dob_match = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", message)
            if dob_match:
                state.dob = f"{dob_match.group(1)}/{dob_match.group(2)}/{dob_match.group(3)}"
            else:
                state.dob = message.strip()

        elif stage == OnboardingStage.PERSONAL_CITY:
            state.city = message.strip()

    def _get_next_stage(self, current: OnboardingStage, state: LumiUserState, message: str) -> OnboardingStage:
        """Determine the next stage based on current stage and user input."""
        stage_order = [
            OnboardingStage.WELCOME,
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
            OnboardingStage.PERSONAL_DOB,
            OnboardingStage.PERSONAL_CITY,
            OnboardingStage.PROCESSING,
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

        return OnboardingStage.PROCESSING

    def _get_stage_buttons(self, stage: OnboardingStage) -> Optional[List[dict]]:
        """Get appropriate buttons for a stage."""
        buttons_map = {
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
            OnboardingStage.LANGUAGE: [
                {"id": "hindi", "title": "Hindi"},
                {"id": "english", "title": "English"},
                {"id": "other", "title": "Other"},
            ],
            OnboardingStage.GENDER_PREFERENCE: [
                {"id": "man", "title": "Man"},
                {"id": "woman", "title": "Woman"},
                {"id": "flexible", "title": "I'm flexible"},
            ],
            OnboardingStage.PERSONAL_CONTEXT: [
                {"id": "single", "title": "Single"},
                {"id": "married", "title": "Married"},
                {"id": "relationship", "title": "In a relationship"},
            ],
        }
        return buttons_map.get(stage)

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
                    messages=[FRICTION_CYCLING_OPTIONS],
                    buttons=[
                        {"id": "talk_to_team", "title": "Talk to Care team"},
                        {"id": "show_more", "title": "Show me more"},
                    ],
                )

            alternatives = get_alternative_therapists(state, exclude_id=state.matched_therapist_id, count=2)
            state.alternative_therapist_ids = [t.id for t in alternatives]
            alt_cards = "\n\n---\n\n".join([format_alternative_card(t) for t in alternatives])

            state.stage = OnboardingStage.ALTERNATIVE_THERAPISTS
            return FlowResponse(
                messages=[f"No problem! Here are two other therapists:\n\n{alt_cards}\n\nStill not sure?\n• Talk to our Care team"],
            )

    def _handle_alternative_therapists(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle alternative therapist selection."""
        message_lower = message.lower()

        if "care team" in message_lower or "talk to" in message_lower:
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = "user_request"
            return FlowResponse(
                messages=[HUMAN_HANDOFF_MESSAGE.format(care_specialist_name="our Care Specialist")],
                is_handoff=True,
                handoff_reason="user_request",
            )

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

            confirmation = STAGE_MESSAGES[OnboardingStage.CONFIRMED].format(
                therapist_name="your matched therapist",
                date="[Date TBD]",
                time="[Time TBD]",
                care_specialist="Our Care Specialist",
                prep_link="[link]",
            )
            return FlowResponse(messages=[confirmation])

        return FlowResponse(
            messages=["Please confirm to proceed with your booking."],
            buttons=[{"id": "confirm", "title": "I confirm"}],
        )

    def _handle_confirmed(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle post-confirmation messages."""
        return FlowResponse(
            messages=["Got questions? Just reply here — I'm always around. 🌱"]
        )


# Module-level handler instance
_handler: Optional[LumiFlowHandler] = None


def get_flow_handler() -> LumiFlowHandler:
    """Get or create the flow handler instance."""
    global _handler
    if _handler is None:
        _handler = LumiFlowHandler()
    return _handler

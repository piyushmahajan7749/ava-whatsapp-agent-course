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

        # Check for handoff keywords
        handoff_decision = should_handoff(message_text)
        if handoff_decision.should_handoff:
            logger.info(f"[LUMI_FLOW] Handoff triggered: {handoff_decision.reason}")
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = handoff_decision.reason
            save_user_state(state)
            return FlowResponse(
                messages=[HUMAN_HANDOFF_MESSAGE],
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

        # Move to demographics after welcome
        state.stage = OnboardingStage.DEMOGRAPHICS

        return FlowResponse(messages=[welcome_text])

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

        # Book a call / Talk to team -> Calendar handoff
        if message_lower in ("book a call", "talk to care team"):
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = "user_request"
            return FlowResponse(
                messages=[
                    HUMAN_HANDOFF_MESSAGE,
                    "I'm handing you over to our Care team now. If you need me again, just send a message anytime!",
                ],
                is_handoff=True,
                handoff_reason="user_request",
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
            except Exception:
                logger.warning("[LUMI_FLOW] FAQ response failed, continuing with normal flow")

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

        # Handle processing (therapist matching)
        if next_stage == OnboardingStage.PROCESSING:
            return await self._handle_processing(state, message)

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
        """Get appropriate buttons for a stage (max 3, for WhatsApp reply buttons)."""
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
            state.stage = OnboardingStage.HUMAN_HANDOFF
            state.handoff_reason = "user_request"
            return FlowResponse(
                messages=[
                    HUMAN_HANDOFF_MESSAGE,
                    "I'm handing you over to our Care team now. If you need me again, just send a message anytime!",
                ],
                is_handoff=True,
                handoff_reason="user_request",
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

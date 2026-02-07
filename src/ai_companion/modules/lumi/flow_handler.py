"""
Lumi onboarding flow handler.

Manages stage transitions, processes user input, and generates responses
for the 15-stage onboarding flow.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from ai_companion.modules.lumi.state import (
    OnboardingStage,
    LumiUserState,
    get_user_state,
    save_user_state,
)
from ai_companion.modules.lumi.prompts import (
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
    NUDGE_1,
    NUDGE_2,
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


@dataclass
class FlowResponse:
    """Response from flow handler."""

    messages: List[str]  # Messages to send (may be multiple)
    buttons: Optional[List[dict]] = None  # Optional button options
    is_handoff: bool = False
    handoff_reason: Optional[str] = None
    is_crisis: bool = False
    new_state: Optional[LumiUserState] = None


class LumiFlowHandler:
    """Handler for Lumi onboarding conversation flow."""

    # Concern keywords for detection
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
        logger.info("[LUMI_FLOW] Handler initialized")

    async def handle_message(
        self,
        phone_number: str,
        message_text: str,
        is_button_response: bool = False,
    ) -> FlowResponse:
        """
        Process incoming message and generate response.

        Args:
            phone_number: User's phone number (E.164 without +)
            message_text: User's message text
            is_button_response: Whether this is a button/list selection

        Returns:
            FlowResponse with messages to send and updated state
        """
        # Get or create user state
        state = get_user_state(phone_number)
        if state is None:
            state = LumiUserState(phone_number=phone_number)
            logger.info(f"[LUMI_FLOW] New user: {phone_number}")

        # Update last message timestamp
        state.last_message_at = datetime.now()

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
            logger.info(f"[LUMI_FLOW] Handoff triggered for {phone_number}: {handoff_decision.reason}")
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
            # Add friction checkpoint to messages
            response.messages.append(FRICTION_CHECKPOINT)
            response.buttons = [
                {"id": "continue_lumi", "title": "Keep going with Lumi"},
                {"id": "talk_to_team", "title": "Talk to someone"},
            ]

        # Save updated state
        save_user_state(state)
        response.new_state = state

        return response

    async def _process_stage(
        self,
        state: LumiUserState,
        message: str,
        is_button: bool,
    ) -> FlowResponse:
        """Process message based on current stage."""

        stage = state.stage
        logger.info(f"[LUMI_FLOW] Processing stage {stage} for {state.phone_number}")

        # Stage handlers
        if stage == OnboardingStage.WELCOME:
            return self._handle_welcome(state, message)

        elif stage == OnboardingStage.DEMOGRAPHICS:
            return self._handle_demographics(state, message)

        elif stage == OnboardingStage.STORY:
            return self._handle_story(state, message)

        elif stage == OnboardingStage.THERAPY_HISTORY:
            return self._handle_therapy_history(state, message)

        elif stage == OnboardingStage.CARE_PREFERENCES:
            return self._handle_care_preferences(state, message)

        elif stage == OnboardingStage.MEDICATION:
            return self._handle_medication(state, message)

        elif stage == OnboardingStage.CONCERNS:
            return self._handle_concerns(state, message)

        elif stage == OnboardingStage.LANGUAGE:
            return self._handle_language(state, message)

        elif stage == OnboardingStage.THERAPIST_STYLE:
            return self._handle_therapist_style(state, message)

        elif stage == OnboardingStage.GENDER_PREFERENCE:
            return self._handle_gender_preference(state, message)

        elif stage == OnboardingStage.PERSONAL_CONTEXT:
            return self._handle_personal_context(state, message)

        elif stage == OnboardingStage.PERSONAL_DOB:
            return self._handle_personal_dob(state, message)

        elif stage == OnboardingStage.PERSONAL_CITY:
            return self._handle_personal_city(state, message)

        elif stage == OnboardingStage.MATCH_REVEAL:
            return self._handle_match_reveal(state, message)

        elif stage == OnboardingStage.ALTERNATIVE_THERAPISTS:
            return self._handle_alternative_therapists(state, message)

        elif stage == OnboardingStage.BOOKING:
            return self._handle_booking(state, message)

        elif stage == OnboardingStage.CONFIRMED:
            return self._handle_confirmed(state, message)

        else:
            # Default: send welcome
            return self._send_welcome(state)

    def _send_welcome(self, state: LumiUserState) -> FlowResponse:
        """Send welcome message."""
        state.stage = OnboardingStage.WELCOME
        return FlowResponse(
            messages=[STAGE_MESSAGES[OnboardingStage.WELCOME]],
            buttons=[
                {"id": "sounds_good", "title": "Sounds good!"},
                {"id": "tell_me_more", "title": "Tell me more"},
            ],
        )

    def _handle_welcome(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle welcome stage response."""
        # Any acknowledgment moves to demographics
        state.stage = OnboardingStage.DEMOGRAPHICS
        return FlowResponse(messages=[STAGE_MESSAGES[OnboardingStage.DEMOGRAPHICS]])

    def _handle_demographics(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle demographics (age, gender) input."""
        # Try to extract age and gender from message
        age_match = re.search(r"\b(\d{1,2})\b", message)
        if age_match:
            state.age = int(age_match.group(1))

        # Gender detection
        message_lower = message.lower()
        if any(g in message_lower for g in ["female", "woman", "girl", "she", "her"]):
            state.gender = "woman"
        elif any(g in message_lower for g in ["male", "man", "boy", "he", "him"]):
            state.gender = "man"
        elif any(g in message_lower for g in ["non-binary", "nonbinary", "they", "other"]):
            state.gender = "non-binary"
            state.queer_affirming_flag = True
        elif any(g in message_lower for g in ["trans", "transgender"]):
            state.gender = "transgender"
            state.queer_affirming_flag = True

        # Move to story stage
        state.stage = OnboardingStage.STORY
        return FlowResponse(messages=[STAGE_MESSAGES[OnboardingStage.STORY]])

    def _handle_story(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle user's story input."""
        state.story_text = message

        # Detect concerns from story
        message_lower = message.lower()
        for concern, keywords in self.CONCERN_KEYWORDS.items():
            if any(kw in message_lower for kw in keywords):
                if concern not in state.concerns:
                    state.concerns.append(concern)
                if concern == "trauma":
                    state.trauma_flag = True

        # Generate empathetic acknowledgment
        acknowledgment = STORY_ACKNOWLEDGMENTS.get("default")
        for concern, ack in STORY_ACKNOWLEDGMENTS.items():
            if concern in message_lower or concern in state.concerns:
                acknowledgment = ack
                break

        # Move to therapy history
        state.stage = OnboardingStage.THERAPY_HISTORY
        return FlowResponse(
            messages=[acknowledgment, STAGE_MESSAGES[OnboardingStage.THERAPY_HISTORY]],
            buttons=[
                {"id": "didnt_stick", "title": "Yes, didn't stick"},
                {"id": "helped", "title": "Yes, and it helped"},
                {"id": "new", "title": "No, I'm new"},
            ],
        )

    def _handle_therapy_history(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle therapy history response."""
        message_lower = message.lower()

        if "didn't stick" in message_lower or "didnt_stick" in message_lower or "didn't work" in message_lower:
            state.therapy_history = "didnt_stick"
            followup = THERAPY_HISTORY_FOLLOWUPS["didnt_stick"]
        elif "helped" in message_lower or "yes, and" in message_lower:
            state.therapy_history = "helped"
            followup = THERAPY_HISTORY_FOLLOWUPS["helped"]
        else:
            state.therapy_history = "new"
            followup = THERAPY_HISTORY_FOLLOWUPS["new"]

        state.stage = OnboardingStage.CARE_PREFERENCES
        return FlowResponse(
            messages=[followup, STAGE_MESSAGES[OnboardingStage.CARE_PREFERENCES]],
            buttons=[
                {"id": "full_care", "title": "Full care plan"},
                {"id": "just_therapy", "title": "Just therapy"},
                {"id": "not_sure", "title": "Not sure yet"},
            ],
        )

    def _handle_care_preferences(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle care preference selection."""
        message_lower = message.lower()

        if "full" in message_lower:
            state.care_preference = "full_care"
        elif "just therapy" in message_lower or "just_therapy" in message_lower:
            state.care_preference = "just_therapy"
        else:
            state.care_preference = "not_sure"

        messages = []
        if state.care_preference == "not_sure":
            messages.append(CARE_PREFERENCE_NOT_SURE)

        state.stage = OnboardingStage.MEDICATION
        messages.append(STAGE_MESSAGES[OnboardingStage.MEDICATION])

        return FlowResponse(
            messages=messages,
            buttons=[
                {"id": "yes", "title": "Yes"},
                {"id": "no", "title": "No"},
            ],
        )

    def _handle_medication(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle medication question."""
        message_lower = message.lower()

        if "yes" in message_lower:
            state.on_medication = True
            # Ask for details
            return FlowResponse(messages=[MEDICATION_YES_FOLLOWUP])

        # Check if this is the medication details response
        if state.on_medication and len(message) > 3:
            state.medications = message
            # Flag complex psychiatric if multiple medications mentioned
            if message.count(",") >= 1 or "and" in message_lower:
                state.complex_psychiatric_flag = True

        state.on_medication = state.on_medication or False
        state.stage = OnboardingStage.CONCERNS
        return FlowResponse(messages=[STAGE_MESSAGES[OnboardingStage.CONCERNS]])

    def _handle_concerns(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle concerns selection (multi-select)."""
        # Parse concerns from message
        concern_options = [
            "anxiety", "depression", "grief", "trauma", "relationship",
            "self-esteem", "identity", "emotional regulation", "ocd",
            "eating disorders", "addiction", "sleep", "chronic illness",
            "adhd", "autism", "women's health", "parenting", "cultural",
            "body image", "phobias"
        ]

        message_lower = message.lower()
        for concern in concern_options:
            if concern in message_lower and concern not in state.concerns:
                state.concerns.append(concern)

        # Set flags
        if "trauma" in state.concerns:
            state.trauma_flag = True

        state.stage = OnboardingStage.LANGUAGE
        return FlowResponse(
            messages=[STAGE_MESSAGES[OnboardingStage.LANGUAGE]],
            buttons=[
                {"id": "hindi", "title": "Hindi"},
                {"id": "english", "title": "English"},
                {"id": "other", "title": "Other"},
            ],
        )

    def _handle_language(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle language preference."""
        languages = [
            "hindi", "english", "tamil", "telugu", "bengali",
            "marathi", "gujarati", "kannada", "malayalam", "punjabi"
        ]

        message_lower = message.lower()
        for lang in languages:
            if lang in message_lower:
                state.language = lang.capitalize()
                break

        if not state.language:
            state.language = message.strip().capitalize()

        state.stage = OnboardingStage.THERAPIST_STYLE
        return FlowResponse(messages=[STAGE_MESSAGES[OnboardingStage.THERAPIST_STYLE]])

    def _handle_therapist_style(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle therapist style preferences (multi-select)."""
        style_options = {
            "warm": "Warm & nurturing",
            "structured": "Structured & direct",
            "blend": "Blend of both",
            "queer": "Queer-affirming",
            "trauma": "Trauma-informed",
            "cultural": "Culturally aware",
            "holistic": "Holistic",
            "solution": "Solution-focused",
        }

        message_lower = message.lower()
        for key, value in style_options.items():
            if key in message_lower:
                state.therapist_style.append(value)

        if "queer" in message_lower:
            state.queer_affirming_flag = True

        messages = []
        if "not sure" in message_lower or "help me" in message_lower:
            messages.append(THERAPIST_STYLE_NOT_SURE)

        state.stage = OnboardingStage.GENDER_PREFERENCE
        messages.append(STAGE_MESSAGES[OnboardingStage.GENDER_PREFERENCE])

        return FlowResponse(
            messages=messages,
            buttons=[
                {"id": "man", "title": "Man"},
                {"id": "woman", "title": "Woman"},
                {"id": "flexible", "title": "I'm flexible"},
            ],
        )

    def _handle_gender_preference(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle therapist gender preference."""
        message_lower = message.lower()

        if "man" in message_lower or "male" in message_lower:
            state.therapist_gender_pref = "man"
        elif "woman" in message_lower or "female" in message_lower:
            state.therapist_gender_pref = "woman"
        else:
            state.therapist_gender_pref = "flexible"

        state.stage = OnboardingStage.PERSONAL_CONTEXT
        return FlowResponse(
            messages=[STAGE_MESSAGES[OnboardingStage.PERSONAL_CONTEXT]],
            buttons=[
                {"id": "single", "title": "Single"},
                {"id": "married", "title": "Married"},
                {"id": "relationship", "title": "In a relationship"},
                {"id": "other", "title": "Other"},
            ],
        )

    def _handle_personal_context(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle relationship status."""
        status_options = ["single", "married", "relationship", "separated", "divorced", "widowed"]

        message_lower = message.lower()
        for status in status_options:
            if status in message_lower:
                state.relationship_status = status
                break

        if not state.relationship_status:
            state.relationship_status = "prefer not to say"

        state.stage = OnboardingStage.PERSONAL_DOB
        return FlowResponse(messages=[STAGE_MESSAGES[OnboardingStage.PERSONAL_DOB]])

    def _handle_personal_dob(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle date of birth."""
        # Accept various date formats
        dob_match = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", message)
        if dob_match:
            state.dob = f"{dob_match.group(1)}/{dob_match.group(2)}/{dob_match.group(3)}"
        else:
            state.dob = message.strip()

        state.stage = OnboardingStage.PERSONAL_CITY
        return FlowResponse(messages=[STAGE_MESSAGES[OnboardingStage.PERSONAL_CITY]])

    def _handle_personal_city(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle city input."""
        state.city = message.strip()

        # Move to processing/matching
        state.stage = OnboardingStage.PROCESSING

        # Run matching
        therapist = match_therapist(state)
        state.matched_therapist_id = therapist.id

        # Generate match reveal message
        match_card = format_therapist_card(therapist, state)

        state.stage = OnboardingStage.MATCH_REVEAL
        return FlowResponse(
            messages=[STAGE_MESSAGES[OnboardingStage.PROCESSING], match_card],
            buttons=[
                {"id": "book_session", "title": "Yes, let's book"},
                {"id": "show_options", "title": "Show other options"},
            ],
        )

    def _handle_match_reveal(self, state: LumiUserState, message: str) -> FlowResponse:
        """Handle response to therapist match."""
        message_lower = message.lower()

        if "book" in message_lower or "yes" in message_lower:
            state.stage = OnboardingStage.BOOKING
            return FlowResponse(
                messages=[STAGE_MESSAGES[OnboardingStage.BOOKING]],
                buttons=[
                    {"id": "confirm", "title": "I confirm"},
                ],
            )
        else:
            # Show alternatives
            state.therapist_options_shown_count += 1

            # Check if cycling too much
            if state.therapist_options_shown_count >= 2:
                return FlowResponse(
                    messages=[FRICTION_CYCLING_OPTIONS],
                    buttons=[
                        {"id": "talk_to_team", "title": "Talk to Care team"},
                        {"id": "show_more", "title": "Show me more"},
                    ],
                )

            alternatives = get_alternative_therapists(
                state,
                exclude_id=state.matched_therapist_id,
                count=2,
            )
            state.alternative_therapist_ids = [t.id for t in alternatives]

            alt_cards = "\n\n---\n\n".join([format_alternative_card(t) for t in alternatives])
            message = f"No problem! Here are two other therapists:\n\n{alt_cards}\n\nStill not sure?\n• Talk to our Care team"

            state.stage = OnboardingStage.ALTERNATIVE_THERAPISTS
            return FlowResponse(messages=[message])

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

        # User selected a therapist
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

            # Generate confirmation message (would normally include booking details)
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

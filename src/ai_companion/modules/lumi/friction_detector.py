"""
Friction detection module for Lumi onboarding.

Detects when users are hesitant, confused, or stuck:
- Very short answers
- "I don't know" patterns
- Evasive language
- Long response times
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FrictionDecision:
    """Result of friction detection."""

    is_friction: bool
    friction_type: Optional[str] = None  # "short_answer", "uncertainty", "evasive", "timeout"
    should_offer_handoff: bool = False
    message: Optional[str] = None


# Uncertainty patterns
UNCERTAINTY_PATTERNS = [
    r"\bi don'?t know\b",
    r"\bnot sure\b",
    r"\bmaybe\b",
    r"\bi guess\b",
    r"\bidk\b",
    r"\bwhatever\b",
    r"\bdoesn'?t matter\b",
    r"\bno idea\b",
    r"\bcan'?t decide\b",
    r"\bconfused\b",
    # Hindi/Hinglish
    r"\bpata nahi\b",
    r"\bnahi pata\b",
    r"\bkya pata\b",
    r"\bsamajh nahi\b",
    r"\bconfuse\b",
    r"\bkuch bhi\b",
]

# Evasive patterns
EVASIVE_PATTERNS = [
    r"\bskip\b",
    r"\bnext\b",
    r"\bpass\b",
    r"\blater\b",
    r"\bnone\b",
    r"\bnothing\b",
    r"\bna\b$",
    r"^ok$",
    r"^okay$",
    r"^k$",
    r"^yes$",
    r"^no$",
    r"^\.$",
    r"^\.\.\.$",
    # Hindi/Hinglish
    r"\bchhodo\b",
    r"\bbaad mein\b",
    r"\bkuch nahi\b",
]

# Minimum expected message lengths by stage (characters)
MIN_EXPECTED_LENGTHS = {
    "story": 20,  # Should be at least a sentence
    "medications": 10,  # Drug names
    "concerns": 5,
    "city": 3,
}


class FrictionDetector:
    """Detector for user friction/hesitation patterns."""

    def __init__(
        self,
        short_answer_threshold: int = 5,
        timeout_minutes: int = 5,
    ):
        """
        Initialize friction detector.

        Args:
            short_answer_threshold: Character count below which answer is "short"
            timeout_minutes: Minutes of inactivity to consider as friction
        """
        self.short_answer_threshold = short_answer_threshold
        self.timeout_minutes = timeout_minutes

        self.uncertainty_patterns = [re.compile(p, re.IGNORECASE) for p in UNCERTAINTY_PATTERNS]
        self.evasive_patterns = [re.compile(p, re.IGNORECASE) for p in EVASIVE_PATTERNS]

        logger.info("[FRICTION] Detector initialized")

    def check(
        self,
        message: str,
        stage: Optional[str] = None,
        last_message_at: Optional[datetime] = None,
        short_answer_count: int = 0,
        friction_count: int = 0,
    ) -> FrictionDecision:
        """
        Check if user message indicates friction.

        Args:
            message: User's message text
            stage: Current onboarding stage (for context-aware detection)
            last_message_at: Timestamp of previous message (for timeout detection)
            short_answer_count: Number of short answers so far
            friction_count: Total friction signals detected so far

        Returns:
            FrictionDecision with friction status and handoff recommendation
        """
        if not message:
            return FrictionDecision(is_friction=False)

        message = message.strip()

        # Check for timeout (long pause)
        if last_message_at:
            time_since_last = datetime.now() - last_message_at
            if time_since_last > timedelta(minutes=self.timeout_minutes):
                logger.info(f"[FRICTION] Timeout detected: {time_since_last}")
                return FrictionDecision(
                    is_friction=True,
                    friction_type="timeout",
                    should_offer_handoff=friction_count >= 1,
                    message="Long pause detected",
                )

        # Check for very short answer
        min_length = MIN_EXPECTED_LENGTHS.get(stage, self.short_answer_threshold)
        if len(message) < min_length:
            # Don't flag single-word valid responses like button selections
            if not self._is_valid_short_response(message, stage):
                logger.info(f"[FRICTION] Short answer: '{message}' ({len(message)} chars)")
                new_short_count = short_answer_count + 1
                return FrictionDecision(
                    is_friction=True,
                    friction_type="short_answer",
                    should_offer_handoff=new_short_count >= 2 or friction_count >= 1,
                    message=f"Short answer #{new_short_count}",
                )

        # Check for uncertainty patterns
        for pattern in self.uncertainty_patterns:
            if pattern.search(message):
                logger.info(f"[FRICTION] Uncertainty pattern: {pattern.pattern}")
                return FrictionDecision(
                    is_friction=True,
                    friction_type="uncertainty",
                    should_offer_handoff=friction_count >= 1,
                    message=f"Uncertainty: {pattern.pattern}",
                )

        # Check for evasive patterns
        for pattern in self.evasive_patterns:
            if pattern.search(message):
                # Only flag if it's the entire message
                if pattern.fullmatch(message) or len(message) < 10:
                    logger.info(f"[FRICTION] Evasive pattern: {pattern.pattern}")
                    return FrictionDecision(
                        is_friction=True,
                        friction_type="evasive",
                        should_offer_handoff=friction_count >= 1,
                        message=f"Evasive: {pattern.pattern}",
                    )

        return FrictionDecision(is_friction=False)

    def _is_valid_short_response(self, message: str, stage: Optional[str]) -> bool:
        """
        Check if a short response is valid for the given stage.

        Some stages expect short responses (button selections, yes/no, etc.)
        """
        message_lower = message.lower()

        # Valid button responses
        valid_short_responses = {
            "yes", "no", "ok", "okay", "sure", "cool", "sounds good",
            "man", "woman", "flexible",
            "single", "married", "divorced", "widowed",
            "hindi", "english", "tamil", "telugu", "bengali",
            "new", "helped", "didnt_stick",
        }

        if message_lower in valid_short_responses:
            return True

        # Numbers (for age)
        if message.isdigit() and 10 <= int(message) <= 100:
            return True

        # Date format for DOB
        if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", message):
            return True

        return False


# Module-level instance
_detector: Optional[FrictionDetector] = None


def get_friction_detector() -> FrictionDetector:
    """Get or create the friction detector instance."""
    global _detector
    if _detector is None:
        _detector = FrictionDetector()
    return _detector


def check_for_friction(
    message: str,
    stage: Optional[str] = None,
    last_message_at: Optional[datetime] = None,
    short_answer_count: int = 0,
    friction_count: int = 0,
) -> FrictionDecision:
    """
    Convenience function to check for friction.

    Args:
        message: User's message text
        stage: Current onboarding stage
        last_message_at: Previous message timestamp
        short_answer_count: Short answer count so far
        friction_count: Total friction count so far

    Returns:
        FrictionDecision
    """
    detector = get_friction_detector()
    return detector.check(message, stage, last_message_at, short_answer_count, friction_count)

"""
Crisis detection module for Lumi onboarding.

Detects crisis language (suicidal ideation, self-harm, immediate danger)
and triggers immediate human escalation with crisis resources.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CrisisDecision:
    """Result of crisis detection."""

    is_crisis: bool
    matched_pattern: Optional[str] = None
    severity: str = "none"  # "none", "moderate", "severe"
    recommended_action: str = "continue"  # "continue", "escalate_immediate"


# Crisis keywords and patterns - English
CRISIS_KEYWORDS_ENGLISH = [
    # Suicidal ideation
    "kill myself",
    "end my life",
    "want to die",
    "don't want to live",
    "don't want to be alive",
    "better off dead",
    "no reason to live",
    "no point in living",
    "suicide",
    "suicidal",
    "take my own life",
    "end it all",
    # Self-harm
    "hurt myself",
    "cutting myself",
    "self harm",
    "self-harm",
    "harming myself",
    "burning myself",
    # Overdose/methods
    "overdose",
    "take all my pills",
    "jump off",
    "hang myself",
    # Immediate danger
    "going to kill",
    "planning to die",
    "ready to die",
]

# Crisis keywords - Hindi/Hinglish
CRISIS_KEYWORDS_HINDI = [
    "marna chahta",
    "marna chahti",
    "mar jana chahta",
    "mar jana chahti",
    "zindagi khatam",
    "jeena nahi chahta",
    "jeena nahi chahti",
    "khud ko hurt",
    "khud ko marna",
    "suicide karna",
    "mar jaunga",
    "mar jaungi",
    "jee nahi pata",
    "jee nahi pati",
]

# Severe crisis indicators (immediate escalation)
SEVERE_CRISIS_INDICATORS = [
    "going to kill myself",
    "planning to end",
    "tonight i will",
    "today i will die",
    "this is goodbye",
    "final message",
    "no one will miss me",
    "everyone better without me",
    "have a plan to",
    "already decided to",
    "marna chahta hun aaj",
    "aaj mar jaunga",
]


class CrisisDetector:
    """Detector for crisis language in user messages."""

    def __init__(self):
        """Initialize crisis detector with keyword lists."""
        self.english_keywords = [k.lower() for k in CRISIS_KEYWORDS_ENGLISH]
        self.hindi_keywords = [k.lower() for k in CRISIS_KEYWORDS_HINDI]
        self.severe_indicators = [k.lower() for k in SEVERE_CRISIS_INDICATORS]

        logger.info(
            f"[CRISIS] Detector initialized with {len(self.english_keywords)} English, "
            f"{len(self.hindi_keywords)} Hindi keywords"
        )

    def check(self, message: str) -> CrisisDecision:
        """
        Check if a message contains crisis language.

        Args:
            message: User's message text

        Returns:
            CrisisDecision with crisis status and recommended action
        """
        if not message:
            return CrisisDecision(is_crisis=False)

        message_lower = message.lower()

        # Check severe indicators first (immediate escalation)
        for pattern in self.severe_indicators:
            if pattern in message_lower:
                logger.warning(f"[CRISIS] SEVERE pattern detected: '{pattern}'")
                return CrisisDecision(
                    is_crisis=True,
                    matched_pattern=pattern,
                    severity="severe",
                    recommended_action="escalate_immediate",
                )

        # Check English crisis keywords
        for keyword in self.english_keywords:
            if keyword in message_lower:
                logger.warning(f"[CRISIS] English keyword detected: '{keyword}'")
                return CrisisDecision(
                    is_crisis=True,
                    matched_pattern=keyword,
                    severity="moderate",
                    recommended_action="escalate_immediate",
                )

        # Check Hindi crisis keywords
        for keyword in self.hindi_keywords:
            if keyword in message_lower:
                logger.warning(f"[CRISIS] Hindi keyword detected: '{keyword}'")
                return CrisisDecision(
                    is_crisis=True,
                    matched_pattern=keyword,
                    severity="moderate",
                    recommended_action="escalate_immediate",
                )

        return CrisisDecision(is_crisis=False)


# Module-level instance for convenience
_detector: Optional[CrisisDetector] = None


def get_crisis_detector() -> CrisisDetector:
    """Get or create the crisis detector instance."""
    global _detector
    if _detector is None:
        _detector = CrisisDetector()
    return _detector


def check_for_crisis(message: str) -> CrisisDecision:
    """
    Convenience function to check for crisis language.

    Args:
        message: User's message text

    Returns:
        CrisisDecision
    """
    detector = get_crisis_detector()
    return detector.check(message)

"""
Human handoff detection module.

Detects when a conversation should be handed off to a human agent based on:
- Keywords (talk to manager, call me, human please, etc.)
- Policy/pricing questions
- User explicitly requesting human
- Friction checkpoints
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from ai_companion.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class HandoffDecision:
    """Result of handoff detection."""

    should_handoff: bool
    reason: Optional[str] = None  # "keyword", "policy", "user_request", "friction", "crisis"
    matched_keyword: Optional[str] = None
    context: Optional[str] = None  # Additional context for the handoff


# Default handoff keywords - English
DEFAULT_KEYWORDS_ENGLISH = [
    "talk to manager",
    "talk to human",
    "speak to human",
    "real person",
    "human please",
    "manager please",
    "supervisor",
    "call me",
    "customer support",
    "speak to someone",
    "talk to someone",
    "live agent",
    "live chat",
    "connect me",
    "transfer me",
]

# Default handoff keywords - Hindi/Hinglish
DEFAULT_KEYWORDS_HINDI = [
    "manager se baat",
    "insaan se baat",
    "kisi se baat",
    "customer care",
    "support se baat",
    "call karo",
    "mujhe call",
]

# Policy/pricing trigger keywords
POLICY_KEYWORDS = [
    "refund",
    "money back",
    "cancel",
    "cancellation",
    "complaint",
    "not happy",
    "dissatisfied",
    "terrible",
    "worst",
    "insurance",
    "claim",
    "reimbursement",
    # Hindi
    "paisa wapas",
    "refund chahiye",
    "cancel karna",
]

# User explicit request patterns
USER_REQUEST_PATTERNS = [
    r"talk to (?:the )?(?:care )?team",
    r"connect (?:me )?(?:with|to) (?:the )?team",
    r"want to speak (?:to|with)",
    r"need (?:to )?(?:talk|speak) (?:to|with)",
    r"let me talk",
]


class HandoffDetector:
    """Detector for human handoff triggers."""

    def __init__(self, custom_keywords: Optional[str] = None):
        """
        Initialize handoff detector.

        Args:
            custom_keywords: Comma-separated custom keywords from settings
        """
        self.keywords = []

        # Add default keywords
        self.keywords.extend([k.lower() for k in DEFAULT_KEYWORDS_ENGLISH])
        self.keywords.extend([k.lower() for k in DEFAULT_KEYWORDS_HINDI])

        # Add custom keywords from settings
        if custom_keywords:
            extra = [k.strip().lower() for k in custom_keywords.split(",") if k.strip()]
            self.keywords.extend(extra)

        # Compile patterns
        self.user_request_patterns = [
            re.compile(p, re.IGNORECASE) for p in USER_REQUEST_PATTERNS
        ]

        logger.info(f"[HANDOFF] Detector initialized with {len(self.keywords)} keywords")

    def check(self, message: str) -> HandoffDecision:
        """
        Check if a message triggers handoff.

        Args:
            message: User's message text

        Returns:
            HandoffDecision with handoff status and reason
        """
        if not message:
            return HandoffDecision(should_handoff=False)

        message_lower = message.lower()

        # Check handoff keywords
        for keyword in self.keywords:
            if keyword in message_lower:
                logger.info(f"[HANDOFF] Keyword triggered: '{keyword}'")
                return HandoffDecision(
                    should_handoff=True,
                    reason="keyword",
                    matched_keyword=keyword,
                )

        # Check policy/pricing keywords
        for keyword in POLICY_KEYWORDS:
            if keyword.lower() in message_lower:
                logger.info(f"[HANDOFF] Policy keyword triggered: '{keyword}'")
                return HandoffDecision(
                    should_handoff=True,
                    reason="policy",
                    matched_keyword=keyword,
                    context=f"User asking about: {keyword}",
                )

        # Check user request patterns
        for pattern in self.user_request_patterns:
            if pattern.search(message):
                logger.info(f"[HANDOFF] User request pattern: {pattern.pattern}")
                return HandoffDecision(
                    should_handoff=True,
                    reason="user_request",
                    matched_keyword=pattern.pattern,
                )

        return HandoffDecision(should_handoff=False)

    def check_button_selection(self, selection: str) -> HandoffDecision:
        """
        Check if a button selection triggers handoff.

        Args:
            selection: Button selection text/ID

        Returns:
            HandoffDecision
        """
        handoff_selections = [
            "talk to team",
            "talk to care team",
            "talk to someone",
            "human",
            "care team",
            "support",
        ]

        selection_lower = selection.lower()
        for trigger in handoff_selections:
            if trigger in selection_lower:
                logger.info(f"[HANDOFF] Button selection triggered: '{selection}'")
                return HandoffDecision(
                    should_handoff=True,
                    reason="user_request",
                    matched_keyword=selection,
                    context="User selected handoff option",
                )

        return HandoffDecision(should_handoff=False)


# Module-level detector instance
_detector: Optional[HandoffDetector] = None


def get_handoff_detector() -> HandoffDetector:
    """Get or create the handoff detector instance."""
    global _detector
    if _detector is None:
        custom_keywords = settings.HANDOFF_KEYWORDS if hasattr(settings, "HANDOFF_KEYWORDS") else None
        _detector = HandoffDetector(custom_keywords=custom_keywords)
    return _detector


def should_handoff(message: str) -> HandoffDecision:
    """
    Convenience function to check for handoff triggers.

    Args:
        message: User's message text

    Returns:
        HandoffDecision
    """
    detector = get_handoff_detector()
    return detector.check(message)

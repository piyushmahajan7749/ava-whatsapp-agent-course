"""
Hindi language detection and translation utilities.
"""

import re
import logging

logger = logging.getLogger(__name__)

def contains_hindi(text: str) -> bool:
    """
    Detect if text contains Hindi characters (Devanagari script).
    
    Args:
        text: Input text to check
        
    Returns:
        True if Hindi characters are found, False otherwise
    """
    if not text:
        return False
    
    # Unicode range for Devanagari script (Hindi)
    hindi_pattern = re.compile(r"[\u0900-\u097F]+")
    return bool(hindi_pattern.search(text))


def get_hindi_ratio(text: str) -> float:
    """
    Get the ratio of Hindi characters to total characters in the text.
    
    Args:
        text: Input text to analyze
        
    Returns:
        Float between 0.0 and 1.0 representing the proportion of Hindi characters
    """
    if not text:
        return 0.0
    
    # Count Hindi characters
    hindi_pattern = re.compile(r"[\u0900-\u097F]")
    hindi_chars = len(hindi_pattern.findall(text))
    
    # Count total non-whitespace characters
    total_chars = len(re.sub(r'\s', '', text))
    
    if total_chars == 0:
        return 0.0
    
    return hindi_chars / total_chars


def should_respond_in_hindi(user_messages: list) -> bool:
    """
    Determine if the agent should respond in Hindi based on recent user messages.
    
    Args:
        user_messages: List of recent user messages
        
    Returns:
        True if agent should respond in Hindi, False otherwise
    """
    if not user_messages:
        return False
    
    # Check the last 3 messages for Hindi content
    recent_text = " ".join([msg.content for msg in user_messages[-3:] if hasattr(msg, 'content')])
    
    # If more than 30% of characters are Hindi, respond in Hindi
    hindi_ratio = get_hindi_ratio(recent_text)
    
    logger.debug(f"Hindi detection: ratio={hindi_ratio:.2f}, should_respond_hindi={hindi_ratio > 0.3}")
    
    return hindi_ratio > 0.3

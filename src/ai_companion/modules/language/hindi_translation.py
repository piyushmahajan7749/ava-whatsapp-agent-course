"""
Hindi translation utilities with URL and link preservation.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import deep-translator, fallback to mock if not available
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
    translator = GoogleTranslator(source='auto', target='hi')
except ImportError:
    TRANSLATOR_AVAILABLE = False
    logger.warning("deep-translator not available. Hindi translation will be disabled.")
    translator = None


def extract_preservable_elements(text: str) -> tuple[str, list]:
    """
    Extract URLs, phone numbers, and other elements that should not be translated.
    
    Args:
        text: Input text
        
    Returns:
        Tuple of (text_with_placeholders, list_of_elements)
    """
    elements = []
    modified_text = text
    
    # Pattern for URLs
    url_pattern = re.compile(r'https?://\S+|www\.\S+')
    urls = url_pattern.findall(text)
    for i, url in enumerate(urls):
        placeholder = f"__URL_{i}__"
        elements.append(('url', url, placeholder))
        modified_text = modified_text.replace(url, placeholder)
    
    # Pattern for phone numbers (Indian format)
    phone_pattern = re.compile(r'(\+91[-\s]?)?[6-9]\d{9}')
    phones = phone_pattern.findall(text)
    for i, phone in enumerate(phones):
        if phone:  # Only if phone number was found
            placeholder = f"__PHONE_{i}__"
            elements.append(('phone', phone, placeholder))
            modified_text = modified_text.replace(phone, placeholder)
    
    # Pattern for email addresses
    email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    emails = email_pattern.findall(text)
    for i, email in enumerate(emails):
        placeholder = f"__EMAIL_{i}__"
        elements.append(('email', email, placeholder))
        modified_text = modified_text.replace(email, placeholder)
    
    # Pattern for amounts (₹ symbol and numbers)
    amount_pattern = re.compile(r'₹\s*\d+(?:,\d{3})*(?:\.\d{2})?')
    amounts = amount_pattern.findall(text)
    for i, amount in enumerate(amounts):
        placeholder = f"__AMOUNT_{i}__"
        elements.append(('amount', amount, placeholder))
        modified_text = modified_text.replace(amount, placeholder)
    
    return modified_text, elements


def restore_preservable_elements(text: str, elements: list) -> str:
    """
    Restore preserved elements back into translated text.
    
    Args:
        text: Text with placeholders
        elements: List of (type, original, placeholder) tuples
        
    Returns:
        Text with original elements restored
    """
    restored_text = text
    
    for element_type, original, placeholder in elements:
        restored_text = restored_text.replace(placeholder, original)
    
    return restored_text


def translate_to_hindi(text: str) -> str:
    """
    Translate text to Hindi while preserving URLs, phone numbers, emails, and amounts.
    
    Args:
        text: Text to translate
        
    Returns:
        Translated text with preserved elements
    """
    if not text or not text.strip():
        return text
    
    if not TRANSLATOR_AVAILABLE:
        logger.warning("Translation not available, returning original text")
        return text
    
    try:
        # Extract elements that should not be translated
        text_with_placeholders, elements = extract_preservable_elements(text)
        
        # Translate the text with placeholders
        if text_with_placeholders.strip():
            translated_text = translator.translate(text_with_placeholders)
        else:
            translated_text = text_with_placeholders
        
        # Restore the preserved elements
        final_text = restore_preservable_elements(translated_text, elements)
        
        logger.debug(f"Translated: '{text[:50]}...' -> '{final_text[:50]}...'")
        return final_text
        
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return text  # Return original text if translation fails


def translate_response_if_needed(response_text: str, should_translate: bool) -> str:
    """
    Translate response to Hindi if needed.
    
    Args:
        response_text: Original response text
        should_translate: Whether to translate to Hindi
        
    Returns:
        Translated text if needed, original text otherwise
    """
    if not should_translate:
        return response_text
    
    return translate_to_hindi(response_text)

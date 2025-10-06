"""
Payment verification module using Azure OpenAI Vision.

Analyzes payment screenshots to extract and verify:
- Payment amount
- Transaction status
- Payment app (GPay, PhonePe, Paytm, etc.)
- Transaction details (ID, date, recipient)
"""

import logging
import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from ai_companion.modules.image.image_to_text import ImageToText
from ai_companion.core.knowledge import CONSULTATION_PRICE_INR


logger = logging.getLogger(__name__)


@dataclass
class PaymentDetails:
    """Payment details extracted from screenshot."""
    is_valid: bool
    amount: Optional[int]
    status: str  # success/pending/failed/unknown
    app: Optional[str]  # gpay/phonepe/paytm/other
    transaction_id: Optional[str]
    datetime: Optional[str]
    recipient: Optional[str]
    amount_matches: bool
    confidence: float  # 0.0 to 1.0
    notes: Optional[str]


class PaymentVerifier:
    """Verifies payment screenshots using Azure Vision AI."""
    
    def __init__(self):
        """Initialize the payment verifier."""
        self.vision_analyzer = ImageToText()
        self.expected_amount = CONSULTATION_PRICE_INR
        self.logger = logging.getLogger(__name__)
    
    def _create_verification_prompt(self) -> str:
        """Create a detailed prompt for payment verification."""
        return f"""Analyze this UPI/payment transaction screenshot and extract the following information:

CRITICAL: Look carefully at all visible text, numbers, and UI elements in the image.

Extract these details:
1. **Valid Payment Screenshot?** - Is this a legitimate payment/UPI transaction screenshot? (Yes/No/Uncertain)
2. **Payment Amount** - The exact amount in Rupees (look for ₹ symbol or "Rs" followed by numbers)
3. **Transaction Status** - Success/Completed/Pending/Failed (look for status indicators, checkmarks, or "successful" text)
4. **Payment App** - GPay/PhonePe/Paytm/BHIM/Other (identify from app UI, logo, or colors)
5. **Transaction ID** - Transaction/Reference/UPI ID (usually alphanumeric code)
6. **Date & Time** - When the transaction occurred
7. **Recipient/Beneficiary** - Who received the payment (name or UPI ID)

**Expected Amount:** ₹{self.expected_amount} (for consultation booking)

**Response Format (be precise):**
Valid Payment: [Yes/No/Uncertain]
Amount: ₹[exact number]
Status: [Success/Pending/Failed/Unknown]
App: [app name]
Transaction ID: [ID or "Not visible"]
Date/Time: [datetime or "Not visible"]
Recipient: [name or "Not visible"]
Amount Matches Expected: [Yes/No/Partial - if amount is ₹{self.expected_amount}]

**Verification Notes:**
- If amount is different from ₹{self.expected_amount}, mention the difference
- Note any concerns about image quality, authenticity, or missing information
- Flag any suspicious elements

Please be thorough and accurate in your analysis."""
    
    async def verify_payment_image(self, image_data: bytes) -> PaymentDetails:
        """
        Verify a payment screenshot using vision AI.
        
        Args:
            image_data: Raw image bytes of the payment screenshot
            
        Returns:
            PaymentDetails with extracted information and verification status
        """
        try:
            self.logger.info("Analyzing payment screenshot with Azure Vision AI...")
            
            # Get verification prompt
            prompt = self._create_verification_prompt()
            
            # Analyze image with vision model
            vision_response = await self.vision_analyzer.analyze_image(
                image_data=image_data,
                prompt=prompt
            )
            
            self.logger.info(f"Vision AI response: {vision_response}")
            
            # Parse the vision response
            payment_details = self._parse_vision_response(vision_response)
            
            return payment_details
            
        except Exception as e:
            self.logger.error(f"Error verifying payment screenshot: {e}")
            # Return failed verification
            return PaymentDetails(
                is_valid=False,
                amount=None,
                status="unknown",
                app=None,
                transaction_id=None,
                datetime=None,
                recipient=None,
                amount_matches=False,
                confidence=0.0,
                notes=f"Error during verification: {str(e)}"
            )
    
    def _parse_vision_response(self, response: str) -> PaymentDetails:
        """
        Parse the vision model response to extract payment details.
        
        Args:
            response: Text response from vision model
            
        Returns:
            PaymentDetails object with extracted information
        """
        response_lower = response.lower()
        
        # Extract validation status
        is_valid = "valid payment: yes" in response_lower
        
        # Extract amount using regex
        amount = self._extract_amount(response)
        
        # Extract status
        status = self._extract_status(response)
        
        # Extract app name
        app = self._extract_app(response)
        
        # Extract transaction ID
        transaction_id = self._extract_field(response, ["transaction id:", "transaction id"])
        
        # Extract datetime
        datetime = self._extract_field(response, ["date/time:", "date & time:", "datetime:"])
        
        # Extract recipient
        recipient = self._extract_field(response, ["recipient:", "beneficiary:"])
        
        # Check if amount matches
        amount_matches = False
        if amount:
            amount_matches = abs(amount - self.expected_amount) < 10  # Allow ±₹10 difference
        
        # Calculate confidence based on extracted fields
        confidence = self._calculate_confidence(
            is_valid, amount, status, app, amount_matches
        )
        
        # Extract notes
        notes = self._extract_notes(response)
        
        return PaymentDetails(
            is_valid=is_valid,
            amount=amount,
            status=status,
            app=app,
            transaction_id=transaction_id,
            datetime=datetime,
            recipient=recipient,
            amount_matches=amount_matches,
            confidence=confidence,
            notes=notes
        )
    
    def _extract_amount(self, text: str) -> Optional[int]:
        """Extract payment amount from text."""
        # Look for patterns like "Amount: ₹2100", "Amount: ₹2,100", "₹2100", "Rs 2100"
        patterns = [
            r"amount:\s*₹?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"₹\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            r"rs\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                amount_str = match.group(1).replace(",", "").replace(".", "")
                try:
                    return int(float(amount_str))
                except ValueError:
                    continue
        
        return None
    
    def _extract_status(self, text: str) -> str:
        """Extract transaction status from text."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["success", "successful", "completed", "done"]):
            return "success"
        elif any(word in text_lower for word in ["pending", "processing", "in progress"]):
            return "pending"
        elif any(word in text_lower for word in ["failed", "failure", "declined", "rejected"]):
            return "failed"
        else:
            return "unknown"
    
    def _extract_app(self, text: str) -> Optional[str]:
        """Extract payment app name from text."""
        text_lower = text.lower()
        
        if "gpay" in text_lower or "google pay" in text_lower:
            return "gpay"
        elif "phonepe" in text_lower or "phone pe" in text_lower:
            return "phonepe"
        elif "paytm" in text_lower:
            return "paytm"
        elif "bhim" in text_lower:
            return "bhim"
        elif "app:" in text_lower:
            # Try to extract whatever comes after "App:"
            match = re.search(r"app:\s*(\w+)", text_lower)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_field(self, text: str, field_indicators: list) -> Optional[str]:
        """Extract a specific field from text using multiple indicators."""
        for indicator in field_indicators:
            if indicator in text.lower():
                # Find the text after the indicator
                start_idx = text.lower().find(indicator) + len(indicator)
                # Get text until next newline or end
                end_idx = text.find("\n", start_idx)
                if end_idx == -1:
                    end_idx = len(text)
                
                field_value = text[start_idx:end_idx].strip()
                
                # Check if it's "Not visible" or similar
                if field_value and "not visible" not in field_value.lower():
                    return field_value
        
        return None
    
    def _calculate_confidence(
        self, 
        is_valid: bool, 
        amount: Optional[int], 
        status: str, 
        app: Optional[str],
        amount_matches: bool
    ) -> float:
        """Calculate confidence score based on extracted fields."""
        confidence = 0.0
        
        # Base confidence if valid payment detected
        if is_valid:
            confidence += 0.3
        
        # Add confidence for each extracted field
        if amount is not None:
            confidence += 0.2
        
        if status == "success":
            confidence += 0.2
        elif status != "unknown":
            confidence += 0.1
        
        if app is not None:
            confidence += 0.1
        
        # Major boost if amount matches expected
        if amount_matches:
            confidence += 0.2
        
        return min(confidence, 1.0)  # Cap at 1.0
    
    def _extract_notes(self, text: str) -> Optional[str]:
        """Extract verification notes from response."""
        # Look for notes or additional information section
        keywords = ["notes:", "additional notes:", "verification notes:", "concerns:"]
        
        for keyword in keywords:
            if keyword in text.lower():
                start_idx = text.lower().find(keyword) + len(keyword)
                notes = text[start_idx:].strip()
                if notes:
                    return notes
        
        return None
    
    def verify_from_text_analysis(self, image_analysis_text: str) -> PaymentDetails:
        """
        Fallback verification from existing image analysis text.
        
        Used when image bytes aren't available but image has already been analyzed.
        
        Args:
            image_analysis_text: Pre-existing image analysis text
            
        Returns:
            PaymentDetails with verification results
        """
        self.logger.info("Verifying payment from existing image analysis text...")
        
        # Check for payment indicators
        text_lower = image_analysis_text.lower()
        
        # Simple keyword-based verification
        payment_keywords = ["payment", "upi", "transaction", "gpay", "phonepe", "paytm", "₹", "rupees"]
        has_payment_indicators = sum(1 for kw in payment_keywords if kw in text_lower) >= 2
        
        if not has_payment_indicators:
            return PaymentDetails(
                is_valid=False,
                amount=None,
                status="unknown",
                app=None,
                transaction_id=None,
                datetime=None,
                recipient=None,
                amount_matches=False,
                confidence=0.1,
                notes="No clear payment indicators found in image analysis"
            )
        
        # Extract amount
        amount = self._extract_amount(image_analysis_text)
        
        # Extract status
        status = self._extract_status(image_analysis_text)
        
        # Extract app
        app = self._extract_app(image_analysis_text)
        
        # Check amount match
        amount_matches = False
        if amount:
            amount_matches = abs(amount - self.expected_amount) < 10
        
        # Simple confidence calculation
        confidence = 0.5  # Base for text analysis
        if amount_matches:
            confidence += 0.3
        if status == "success":
            confidence += 0.2
        
        return PaymentDetails(
            is_valid=has_payment_indicators and amount_matches,
            amount=amount,
            status=status,
            app=app,
            transaction_id=None,
            datetime=None,
            recipient=None,
            amount_matches=amount_matches,
            confidence=min(confidence, 1.0),
            notes="Verified from text analysis (image bytes not available)"
        )


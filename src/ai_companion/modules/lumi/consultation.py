"""
Consultation booking API client for Lumi.

Handles fetching available slots and booking consultations via the
Feel Your Best consultation API.
"""

import logging
from datetime import date, datetime, timedelta, time as dt_time
from typing import Dict, List, Optional

import httpx

from ai_companion.settings import settings

logger = logging.getLogger(__name__)

# Business hours: 9 AM - 7 PM IST, Mon-Sat, 30-min slots
BUSINESS_START_HOUR = 9
BUSINESS_END_HOUR = 19
SLOT_DURATION_MINUTES = 30
BUSINESS_DAYS = {0, 1, 2, 3, 4, 5}  # Mon=0 .. Sat=5 (Sunday excluded)


class ConsultationClient:
    """Client for the Feel Your Best consultation booking API."""

    def __init__(self):
        self.base_url = settings.CONSULTATION_API_URL
        self.api_key = settings.CONSULTATION_API_KEY
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def get_booked_slots(self, date_str: str) -> List[dict]:
        """
        Fetch booked events for a given date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            List of booked event dicts from the API, or empty list on error.
        """
        url = f"{self.base_url}/available-slots"
        params = {"date": date_str}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    events = data.get("data", {}).get("events", [])
                    logger.info(
                        f"[CONSULTATION] Got {len(events)} booked events for {date_str}"
                    )
                    return events
                else:
                    logger.error(
                        f"[CONSULTATION] GET slots failed: {response.status_code} - {response.text}"
                    )
                    return []
            except httpx.HTTPError as e:
                logger.error(f"[CONSULTATION] HTTP error getting slots: {e}")
                return []

    def calculate_available_slots(
        self,
        booked_events: List[dict],
        target_date: date,
    ) -> List[str]:
        """
        Calculate available 30-min slots by finding gaps in booked events.

        Generates all possible slots (9AM-7PM, Mon-Sat), subtracts booked ones.
        If target_date is today, filters out past slots with a 30-min buffer.

        Args:
            booked_events: List of booked event dicts from the API
            target_date: The date to calculate slots for

        Returns:
            List of available time strings in "HH:MM" format
        """
        if target_date.weekday() not in BUSINESS_DAYS:
            return []

        # Generate all possible 30-min slots
        all_slots = []
        total_minutes = BUSINESS_START_HOUR * 60
        end_minutes = BUSINESS_END_HOUR * 60
        while total_minutes < end_minutes:
            h, m = divmod(total_minutes, 60)
            all_slots.append(f"{h:02d}:{m:02d}")
            total_minutes += SLOT_DURATION_MINUTES

        # Extract booked times from events
        booked_times = set()
        for event in booked_events:
            start = event.get("start", {})
            start_dt = start.get("dateTime", "")
            if start_dt:
                # Parse "2026-02-15T10:00:00+05:30" -> "10:00"
                try:
                    t = datetime.fromisoformat(start_dt)
                    booked_times.add(f"{t.hour:02d}:{t.minute:02d}")
                except (ValueError, TypeError):
                    pass

        # Remove booked slots
        available = [s for s in all_slots if s not in booked_times]

        # If today, filter out past slots (with 30-min buffer)
        if target_date == date.today():
            now = datetime.now()
            buffer_minutes = now.hour * 60 + now.minute + 30
            available = [
                s
                for s in available
                if int(s[:2]) * 60 + int(s[3:]) >= buffer_minutes
            ]

        return available

    async def book_slot(
        self,
        phone: str,
        name: str,
        meeting_date: str,
        meeting_time: str,
    ) -> Dict:
        """
        Book a consultation slot.

        Args:
            phone: Phone number in E.164 format (e.g., "+919303402193")
            name: User's name
            meeting_date: Date in YYYY-MM-DD format
            meeting_time: Time in HH:MM format

        Returns:
            Dict with "status_code" and "response" keys
        """
        url = f"{self.base_url}/book-slot"
        payload = {
            "phone": phone,
            "name": name,
            "meetingDate": meeting_date,
            "meetingTime": meeting_time,
        }

        logger.info(
            f"[CONSULTATION] Booking slot: {meeting_date} {meeting_time} for {phone}"
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    url, headers=self.headers, json=payload
                )
                result = response.json() if response.content else {}
                logger.info(
                    f"[CONSULTATION] Book response: {response.status_code}"
                )
                if response.status_code not in (200, 201):
                    logger.error(
                        f"[CONSULTATION] Book failed: {response.status_code} - {result}"
                    )
                return {"status_code": response.status_code, "response": result}
            except httpx.HTTPError as e:
                logger.error(f"[CONSULTATION] HTTP error booking: {e}")
                raise


def get_upcoming_dates(count: int = 3) -> List[dict]:
    """
    Get the next N available business days (Mon-Sat) as button-friendly dicts.

    Returns max 3 entries (WhatsApp button limit).

    Returns:
        List of dicts: [{"date": "2026-02-12", "label": "Today (Thu, 12 Feb)"}, ...]
    """
    dates = []
    current = date.today()

    for _ in range(count + 7):  # Extra iterations to skip Sundays
        if len(dates) >= count:
            break
        if current.weekday() in BUSINESS_DAYS:
            if current == date.today():
                label = f"Today ({current.strftime('%a, %d %b')})"
            elif current == date.today() + timedelta(days=1):
                label = f"Tomorrow ({current.strftime('%a, %d %b')})"
            else:
                label = current.strftime("%a, %d %b")
            dates.append({"date": current.isoformat(), "label": label})
        current += timedelta(days=1)

    return dates[:count]


def format_time_label(time_str: str) -> str:
    """Format 'HH:MM' into '9:00 AM' style for WhatsApp display."""
    hour, minute = int(time_str[:2]), int(time_str[3:])
    period = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {period}"


# Singleton client instance
_client: Optional[ConsultationClient] = None


def get_consultation_client() -> Optional[ConsultationClient]:
    """Get or create consultation client. Returns None if not configured."""
    global _client
    if not settings.CONSULTATION_API_KEY:
        logger.warning("[CONSULTATION] Not configured (missing CONSULTATION_API_KEY)")
        return None
    if _client is None:
        _client = ConsultationClient()
    return _client

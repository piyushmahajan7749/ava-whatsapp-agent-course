"""Google Calendar integration tools for checking availability and booking events."""

import logging
from datetime import datetime, timezone, time
from typing import Annotated

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from googleapiclient.errors import HttpError

from ai_companion.modules.calendar.auth import get_calendar_service
from ai_companion.modules.sheets.sheets_manager import log_consultation_booking, log_product_order

logger = logging.getLogger(__name__)

# Global state holders for payment verification
_payment_verification_state = {}  # thread_id -> bool (verified or not)
_payment_history = {}  # thread_id -> list of payment amounts

# Allowed time slots for consultations
ALLOWED_TIME_SLOTS = [
    (time(9, 0), time(12, 0)),   # 9:00 AM to 12:00 PM
    (time(14, 0), time(16, 0)),  # 2:00 PM to 4:00 PM  
    (time(18, 0), time(20, 0)),  # 6:00 PM to 8:00 PM
]


def validate_time_slot(start_dt: datetime, end_dt: datetime) -> tuple[bool, str]:
    """
    Validate that the requested time slot falls within allowed consultation hours.
    
    Args:
        start_dt: Start datetime
        end_dt: End datetime
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Extract time components (ignore date)
    start_time = start_dt.time()
    end_time = end_dt.time()
    
    # Check if start time falls within any allowed slot
    start_valid = False
    for slot_start, slot_end in ALLOWED_TIME_SLOTS:
        if slot_start <= start_time < slot_end:
            start_valid = True
            # Check if end time is also within the same slot
            if end_time <= slot_end:
                return True, ""
            else:
                return False, f"End time {end_time.strftime('%I:%M %p')} extends beyond allowed slot ending at {slot_end.strftime('%I:%M %p')}"
    
    if not start_valid:
        # Format allowed slots for error message
        allowed_slots_str = ", ".join([
            f"{slot_start.strftime('%I:%M %p')}-{slot_end.strftime('%I:%M %p')}" 
            for slot_start, slot_end in ALLOWED_TIME_SLOTS
        ])
        return False, f"Start time {start_time.strftime('%I:%M %p')} is not within allowed consultation hours. Available slots: {allowed_slots_str}"
    
    return True, ""


def get_available_slots_for_date(date: datetime) -> list:
    """
    Get all available time slots for a given date.
    
    Args:
        date: The date to check slots for
        
    Returns:
        List of available time slots as (start_time, end_time) tuples
    """
    available_slots = []
    
    for slot_start, slot_end in ALLOWED_TIME_SLOTS:
        # Create datetime objects for the specific date
        start_dt = datetime.combine(date.date(), slot_start)
        end_dt = datetime.combine(date.date(), slot_end)
        
        # Add timezone if the input date has one
        if date.tzinfo:
            start_dt = start_dt.replace(tzinfo=date.tzinfo)
            end_dt = end_dt.replace(tzinfo=date.tzinfo)
        
        available_slots.append((start_dt, end_dt))
    
    return available_slots


@tool
def check_calendar_availability(
    start_time: Annotated[str, "Start time in ISO format with timezone (e.g., '2025-10-05T10:00:00+05:30')"],
    end_time: Annotated[str, "End time in ISO format with timezone (e.g., '2025-10-05T11:00:00+05:30')"],
) -> str:
    """
    Check if a time slot is available in the calendar.
    
    Args:
        start_time: The start time of the slot in ISO format with timezone
        end_time: The end time of the slot in ISO format with timezone
    
    Returns:
        A message indicating whether the slot is available or not
    """
    logger.info(f"Checking availability from {start_time} to {end_time}")
    
    try:
        # Validate and normalize datetime format
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # Ensure timezone-aware datetimes (default to IST if not specified)
        if start_dt.tzinfo is None:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            start_dt = ist.localize(start_dt)
        if end_dt.tzinfo is None:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            end_dt = ist.localize(end_dt)
        
        # Validate time slot is within allowed consultation hours
        is_valid, error_message = validate_time_slot(start_dt, end_dt)
        if not is_valid:
            return f"❌ {error_message}"
        
        # Format for API (RFC3339)
        start_time_formatted = start_dt.isoformat()
        end_time_formatted = end_dt.isoformat()
        
        # Get authenticated service
        service = get_calendar_service()
        
        # Query calendar for events in the time range
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_time_formatted,
            timeMax=end_time_formatted,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"✅ The time slot from {start_time} to {end_time} is available."
        else:
            # List conflicting events
            conflicts = []
            for event in events:
                event_summary = event.get('summary', 'Untitled Event')
                event_start = event['start'].get('dateTime', event['start'].get('date'))
                conflicts.append(f"  - {event_summary} at {event_start}")
            
            conflicts_str = "\n".join(conflicts)
            return (
                f"❌ The time slot is not available. Found {len(events)} conflicting event(s):\n"
                f"{conflicts_str}"
            )
        
    except ValueError as e:
        logger.error(f"Invalid datetime format: {e}")
        return f"Error: Invalid datetime format. Please use ISO format with timezone (e.g., '2025-10-05T10:00:00+05:30'). Details: {str(e)}"
    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        return f"Error accessing Google Calendar: {e.reason}. Please check your permissions."
    except FileNotFoundError as e:
        logger.error(f"Credentials file not found: {e}")
        return str(e)
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}", exc_info=True)
        return f"Error checking calendar availability: {str(e)}"


@tool
def book_calendar_event(
    start_time: Annotated[str, "Start time in ISO format with timezone (e.g., '2025-10-05T10:00:00+05:30')"],
    end_time: Annotated[str, "End time in ISO format with timezone (e.g., '2025-10-05T11:00:00+05:30')"],
    event_title: Annotated[str, "Title of the event"],
    event_description: Annotated[str, "Description of the event"] = "",
    attendee_email: Annotated[str, "Email of the attendee (optional)"] = "",
    config: RunnableConfig = None,
) -> str:
    """
    Book an event in the calendar. IMPORTANT: Payment verification is required before booking.
    
    The user MUST send a payment screenshot before this tool can successfully book an appointment.
    If payment has not been verified, this tool will return an error asking for payment proof.
    
    Args:
        start_time: The start time of the event in ISO format with timezone
        end_time: The end time of the event in ISO format with timezone
        event_title: The title/summary of the event
        event_description: Additional details about the event
        attendee_email: Email address of attendee to invite (optional)
    
    Returns:
        A confirmation message with event details, or an error if payment not verified
    """
    logger.info(f"Booking event '{event_title}' from {start_time} to {end_time}")
    
    # Get thread_id from config parameter
    thread_id = None
    if config:
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id:
            logger.info(f"Retrieved thread_id from config: {thread_id}")
        else:
            logger.warning("Config provided but no thread_id found")
    else:
        logger.warning("No config provided - skipping payment check")
    
    # Check payment verification if we have a thread_id
    if thread_id:
        payment_verified = _payment_verification_state.get(thread_id, False)
        
        if not payment_verified:
            logger.warning(f"Booking attempt without payment verification for thread {thread_id}")
            return (
                "❌ Payment verification required before booking.\n\n"
                "Please send a screenshot of your payment transaction first. "
                "Once I verify your payment, I'll proceed with booking your appointment.\n\n"
                "You can send the payment screenshot by uploading an image showing:\n"
                "- Payment confirmation from UPI app (GPay, PhonePe, Paytm, etc.)\n"
                "- Transaction details including amount and status\n"
                "- Payment successful message"
            )
    else:
        logger.warning("No thread_id available - skipping payment verification check")
    
    try:
        # Validate and normalize datetime format
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        # Validate that end time is after start time
        if end_dt <= start_dt:
            return "❌ Error: End time must be after start time."
        
        # Ensure timezone-aware datetimes (default to IST if not specified)
        if start_dt.tzinfo is None:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            start_dt = ist.localize(start_dt)
        if end_dt.tzinfo is None:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            end_dt = ist.localize(end_dt)
        
        # Validate time slot is within allowed consultation hours
        is_valid, error_message = validate_time_slot(start_dt, end_dt)
        if not is_valid:
            return f"❌ {error_message}"
        
        # Format for API
        start_time_formatted = start_dt.isoformat()
        end_time_formatted = end_dt.isoformat()
        
        # Use Asia/Kolkata timezone name for Google Calendar
        timezone_str = 'Asia/Kolkata'
        
        # Get authenticated service
        service = get_calendar_service()
        
        # Construct event object
        event = {
            'summary': event_title,
            'description': event_description,
            'start': {
                'dateTime': start_time_formatted,
                'timeZone': timezone_str,
            },
            'end': {
                'dateTime': end_time_formatted,
                'timeZone': timezone_str,
            },
        }
        
        # Add attendee if provided
        if attendee_email:
            event['attendees'] = [{'email': attendee_email}]
            # Send notifications to attendees
            event['sendNotifications'] = True
        
        # Create the event
        created_event = service.events().insert(
            calendarId='primary',
            body=event,
            sendUpdates='all' if attendee_email else 'none'
        ).execute()
        
        event_id = created_event.get('id')
        event_link = created_event.get('htmlLink')
        
        # 🆕 Log booking to Google Sheets for business records
        try:
            # Get payment details for split payment tracking (if we have thread_id)
            payment_summary = None
            payment_details = None
            payment_amount = 2100  # Default consultation price
            
            if thread_id:
                payment_summary = get_payment_total(thread_id)
                payment_amount = payment_summary['total']
                if payment_summary['count'] > 1:
                    # Format split payment details: "2000 + 100"
                    payment_details = " + ".join([str(p) for p in payment_summary['payments']])
            
            # Extract customer name from event title
            # Format is usually "Consultation - [Name]" or just the name
            customer_name = event_title.replace("Consultation - ", "").replace("Consultation with ", "").replace("Audio Consultation with Guru Maa for ", "")
            
            # Log consultation booking to Sheets
            sheets_result = log_consultation_booking(
                customer_name=customer_name,
                date_of_birth="",  # Could be extracted from description if stored
                consultation_datetime=start_time_formatted,
                payment_amount=payment_amount,
                payment_details=payment_details,
                calendar_event_id=event_id,
                calendar_link=event_link,
                thread_id=thread_id or "",
                contact_info=attendee_email if attendee_email else "",
                notes=event_description,
            )
            
            if sheets_result['success']:
                logger.info(f"📊 Booking logged to Sheets: {sheets_result['booking_id']}")
            else:
                logger.warning(f"⚠️  Failed to log booking to Sheets: {sheets_result.get('error')}")
                # Don't fail the booking if Sheets write fails - it's supplementary
                
        except Exception as e:
            logger.error(f"Error logging booking to Sheets: {e}", exc_info=True)
            # Continue - Sheets logging is supplementary, don't block calendar booking
        
        attendee_info = f" with attendee {attendee_email}" if attendee_email else ""
        return (
            f"✅ Event '{event_title}' successfully booked from {start_time} to {end_time}{attendee_info}.\n"
            f"Event ID: {event_id}\n"
            f"View in Google Calendar: {event_link}"
        )
        
    except ValueError as e:
        logger.error(f"Invalid datetime format: {e}")
        return f"❌ Error: Invalid datetime format. Please use ISO format with timezone (e.g., '2025-10-05T10:00:00+05:30'). Details: {str(e)}"
    except HttpError as e:
        logger.error(f"Google Calendar API error: {e}")
        return f"❌ Error creating calendar event: {e.reason}. Please check your permissions."
    except FileNotFoundError as e:
        logger.error(f"Credentials file not found: {e}")
        return str(e)
    except Exception as e:
        logger.error(f"Error booking event: {str(e)}", exc_info=True)
        return f"❌ Error booking calendar event: {str(e)}"


@tool
def get_available_consultation_slots(
    date: Annotated[str, "Date in YYYY-MM-DD format (e.g., '2025-10-15')"],
    timezone_str: Annotated[str, "Timezone (e.g., 'Asia/Kolkata')"] = "Asia/Kolkata"
) -> str:
    """
    Get all available consultation time slots for a specific date.
    
    This tool shows the standard consultation hours and checks which slots
    are available on the calendar for booking.
    
    Args:
        date: The date to check in YYYY-MM-DD format
        timezone_str: Timezone for the date (defaults to Asia/Kolkata)
    
    Returns:
        A formatted message showing available time slots
    """
    logger.info(f"Getting available consultation slots for {date}")
    
    try:
        import pytz
        
        # Parse the date
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get timezone
        tz = pytz.timezone(timezone_str)
        
        # Create datetime for the start of the day
        day_start = tz.localize(datetime.combine(date_obj, time(0, 0)))
        
        # Get all possible consultation slots for this date
        available_slots = get_available_slots_for_date(day_start)
        
        # Check each slot against the calendar
        service = get_calendar_service()
        available_slots_info = []
        
        for slot_start, slot_end in available_slots:
            # Check if this slot is free
            events_result = service.events().list(
                calendarId='primary',
                timeMin=slot_start.isoformat(),
                timeMax=slot_end.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if not events:
                # Slot is available
                start_time_str = slot_start.strftime('%I:%M %p')
                end_time_str = slot_end.strftime('%I:%M %p')
                available_slots_info.append(f"✅ {start_time_str} - {end_time_str}")
            else:
                # Slot is booked
                start_time_str = slot_start.strftime('%I:%M %p')
                end_time_str = slot_end.strftime('%I:%M %p')
                event_summary = events[0].get('summary', 'Booked')
                available_slots_info.append(f"❌ {start_time_str} - {end_time_str} (Booked: {event_summary})")
        
        # Format the response
        date_formatted = day_start.strftime('%A, %B %d, %Y')
        slots_text = "\n".join(available_slots_info)
        
        return (
            f"📅 Available consultation slots for {date_formatted}:\n\n"
            f"{slots_text}\n\n"
            f"💡 Standard consultation hours:\n"
            f"• Morning: 9:00 AM - 12:00 PM\n"
            f"• Afternoon: 2:00 PM - 4:00 PM\n"
            f"• Evening: 6:00 PM - 8:00 PM"
        )
        
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        return f"❌ Error: Invalid date format. Please use YYYY-MM-DD format (e.g., '2025-10-15'). Details: {str(e)}"
    except Exception as e:
        logger.error(f"Error getting available slots: {str(e)}", exc_info=True)
        return f"❌ Error getting available consultation slots: {str(e)}"


@tool
def log_product_order_to_sheets(
    product_type: Annotated[str, "Type of product (e.g., 'Apamarg Jad Kalawa', 'Yantra', 'Puja')"],
    product_name: Annotated[str, "Specific product name (e.g., 'Kalawa - Blessed on Purnima')"],
    customer_name: Annotated[str, "Full name of the customer"],
    payment_amount: Annotated[int, "Amount paid in rupees"],
    shipping_address: Annotated[str, "Complete shipping address for delivery"],
    gotra: Annotated[str, "Family lineage/gotra (if provided)"] = "",
    contact_info: Annotated[str, "Phone number or email address"] = "",
    payment_details: Annotated[str, "Payment breakdown if split payment (e.g., '2000 + 100')"] = "",
    puja_date: Annotated[str, "Date of puja/blessing (if applicable)"] = "",
    thread_id: Annotated[str, "User session identifier"] = "",
    notes: Annotated[str, "Additional notes or special instructions"] = "",
    config: RunnableConfig = None,
) -> str:
    """
    Log a product/puja order to Google Sheets for business tracking.
    
    This tool should be called when a customer completes a product order or puja booking
    to create a record in the business spreadsheet for order fulfillment.
    
    Args:
        product_type: Type of product (Kalawa, Yantra, Puja, etc.)
        product_name: Specific product name
        customer_name: Full name of customer
        payment_amount: Amount paid in rupees
        shipping_address: Complete delivery address
        gotra: Family lineage (optional)
        contact_info: Phone or email (optional)
        payment_details: Split payment breakdown (optional)
        puja_date: Date of puja/blessing (optional)
        thread_id: User session ID (optional)
        notes: Additional notes (optional)
        
    Returns:
        Success message with order ID or error message
    """
    try:
        # Get thread_id from config if not provided
        if not thread_id and config:
            thread_id = config.get("configurable", {}).get("thread_id", "")
        
        result = log_product_order(
            product_type=product_type,
            product_name=product_name,
            customer_name=customer_name,
            payment_amount=payment_amount,
            shipping_address=shipping_address,
            gotra=gotra or None,
            contact_info=contact_info or None,
            payment_details=payment_details or None,
            puja_date=puja_date or None,
            thread_id=thread_id or None,
            notes=notes or None,
        )
        
        if result.get("success"):
            order_id = result.get("order_id", "Unknown")
            return f"✅ Product order logged successfully! Order ID: {order_id}. The order has been recorded in our system for processing."
        else:
            error = result.get("error", "Unknown error")
            return f"❌ Failed to log product order: {error}"
            
    except Exception as e:
        logger.error(f"Error logging product order: {e}", exc_info=True)
        return f"❌ Error logging product order: {str(e)}"


def get_calendar_tools():
    """Return a list of all calendar and sheets tools."""
    return [
        check_calendar_availability, 
        book_calendar_event, 
        get_available_consultation_slots,
        log_product_order_to_sheets
    ]


def set_payment_verified(thread_id: str, verified: bool = True):
    """Set payment verification status for a specific thread/user."""
    global _payment_verification_state
    _payment_verification_state[thread_id] = verified
    logger.info(f"Payment verification set to {verified} for thread {thread_id}")


def get_payment_verified(thread_id: str) -> bool:
    """Check if payment has been verified for a specific thread/user."""
    return _payment_verification_state.get(thread_id, False)


def add_payment_amount(thread_id: str, amount: int) -> dict:
    """
    Add a payment amount to the history for a thread.
    
    Handles split payments by tracking multiple payment screenshots.
    
    Args:
        thread_id: User/thread identifier
        amount: Payment amount in Rupees
        
    Returns:
        dict with:
            - total: Total amount paid so far
            - payments: List of individual payment amounts
            - count: Number of payments
            - fully_paid: Whether total >= expected amount
    """
    global _payment_history
    
    if thread_id not in _payment_history:
        _payment_history[thread_id] = []
    
    _payment_history[thread_id].append(amount)
    
    total = sum(_payment_history[thread_id])
    expected = 2100  # Consultation price
    
    result = {
        "total": total,
        "payments": _payment_history[thread_id].copy(),
        "count": len(_payment_history[thread_id]),
        "fully_paid": total >= expected,
        "expected": expected,
        "remaining": max(0, expected - total)
    }
    
    logger.info(
        f"Payment history for thread {thread_id}: "
        f"{len(_payment_history[thread_id])} payment(s), "
        f"Total: ₹{total}, Expected: ₹{expected}, Remaining: ₹{result['remaining']}"
    )
    
    return result


def get_payment_total(thread_id: str) -> dict:
    """
    Get total payment amount for a thread.
    
    Returns:
        dict with payment summary
    """
    global _payment_history
    
    if thread_id not in _payment_history or not _payment_history[thread_id]:
        return {
            "total": 0,
            "payments": [],
            "count": 0,
            "fully_paid": False,
            "expected": 2100,
            "remaining": 2100
        }
    
    total = sum(_payment_history[thread_id])
    expected = 2100
    
    return {
        "total": total,
        "payments": _payment_history[thread_id].copy(),
        "count": len(_payment_history[thread_id]),
        "fully_paid": total >= expected,
        "expected": expected,
        "remaining": max(0, expected - total)
    }


def clear_payment_history(thread_id: str):
    """Clear payment history for a thread (after successful booking)."""
    global _payment_history
    if thread_id in _payment_history:
        del _payment_history[thread_id]
        logger.info(f"Cleared payment history for thread {thread_id}")

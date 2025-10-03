"""Google Calendar integration tools for checking availability and booking events."""

import logging
from datetime import datetime, timezone
from typing import Annotated

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from googleapiclient.errors import HttpError

from ai_companion.modules.calendar.auth import get_calendar_service

logger = logging.getLogger(__name__)

# Global state holder for payment verification
_payment_verification_state = {}


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
    
    # Check payment verification status
    # We'll use a simpler approach: check if payment verification was recorded
    # The state will be set by the payment_verification_node
    from langchain_core.runnables import RunnableConfig
    config = RunnableConfig.get()
    thread_id = config.get("configurable", {}).get("thread_id") if config else None
    
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


def get_calendar_tools():
    """Return a list of all calendar tools."""
    return [check_calendar_availability, book_calendar_event]


def set_payment_verified(thread_id: str, verified: bool = True):
    """Set payment verification status for a specific thread/user."""
    global _payment_verification_state
    _payment_verification_state[thread_id] = verified
    logger.info(f"Payment verification set to {verified} for thread {thread_id}")


def get_payment_verified(thread_id: str) -> bool:
    """Check if payment has been verified for a specific thread/user."""
    return _payment_verification_state.get(thread_id, False)

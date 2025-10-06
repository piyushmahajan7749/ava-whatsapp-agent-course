"""Core Google Sheets manager for logging bookings."""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from ai_companion.modules.calendar.auth import get_sheets_service

logger = logging.getLogger(__name__)

# Sheet names
CONSULTATIONS_SHEET_NAME = "Consultations"
PRODUCTS_SHEET_NAME = "Products"


def get_sheets_config() -> Dict[str, str]:
    """
    Get Sheets configuration from settings.
    
    Returns:
        dict with spreadsheet_id and sheet names
        
    Raises:
        ValueError: If GOOGLE_SHEETS_BOOKING_ID not set
    """
    from ai_companion.settings import settings
    
    spreadsheet_id = settings.GOOGLE_SHEETS_BOOKING_ID
    
    if not spreadsheet_id:
        raise ValueError(
            "GOOGLE_SHEETS_BOOKING_ID not set in .env file. "
            "Please create a Google Sheet and set its ID in .env file.\n"
            "Example: GOOGLE_SHEETS_BOOKING_ID='1abc...xyz'\n"
            "You can find the ID in the sheet URL: "
            "https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
        )
    
    return {
        "spreadsheet_id": spreadsheet_id,
        "consultations_sheet": CONSULTATIONS_SHEET_NAME,
        "products_sheet": PRODUCTS_SHEET_NAME,
    }


def _generate_booking_id(booking_type: str) -> str:
    """
    Generate unique booking ID.
    
    Args:
        booking_type: Either 'consultation' or 'product'
        
    Returns:
        Unique booking ID like CONS_20251006_083015
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    prefix = "CONS" if booking_type == "consultation" else "PROD"
    return f"{prefix}_{date_str}_{time_str}"


def log_consultation_booking(
    customer_name: str,
    date_of_birth: str,
    consultation_datetime: str,
    payment_amount: int,
    payment_details: Optional[str] = None,
    calendar_event_id: Optional[str] = None,
    calendar_link: Optional[str] = None,
    thread_id: Optional[str] = None,
    contact_info: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a consultation booking to Google Sheets.
    
    This function appends a new row to the "Consultations" sheet with all
    booking details including payment information, calendar event, and
    customer information.
    
    Args:
        customer_name: Full name of customer
        date_of_birth: Date of birth for consultation
        consultation_datetime: Scheduled datetime in ISO format
        payment_amount: Total amount paid in rupees
        payment_details: Payment breakdown if split (e.g., "2000 + 100")
        calendar_event_id: Google Calendar event ID
        calendar_link: Link to calendar event
        thread_id: User session identifier
        contact_info: Phone or email
        notes: Additional notes
        
    Returns:
        dict with:
            - success: bool
            - booking_id: str (if success)
            - row_number: int (if success)
            - error: str (if failure)
            
    Example:
        >>> result = log_consultation_booking(
        ...     customer_name="Rahul Sharma",
        ...     date_of_birth="1990-05-15",
        ...     consultation_datetime="2025-10-08T10:00:00+05:30",
        ...     payment_amount=2100,
        ...     payment_details="2000 + 100",
        ...     calendar_event_id="abc123",
        ...     thread_id="user_123"
        ... )
        >>> print(result['booking_id'])
        'CONS_20251006_083015'
    """
    try:
        config = get_sheets_config()
        service = get_sheets_service()
        
        # Generate booking ID
        booking_id = _generate_booking_id("consultation")
        
        # Parse consultation datetime
        try:
            consult_dt = datetime.fromisoformat(consultation_datetime.replace('Z', '+00:00'))
            consult_date = consult_dt.strftime("%Y-%m-%d")
            consult_time = consult_dt.strftime("%I:%M %p")
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{consultation_datetime}': {e}")
            consult_date = consultation_datetime
            consult_time = ""
        
        # Determine if split payment
        is_split = payment_details is not None and "+" in str(payment_details)
        
        # Prepare row data (matches sheet schema)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            timestamp,                           # Timestamp
            booking_id,                          # Booking ID
            customer_name,                       # Customer Name
            date_of_birth,                       # Date of Birth
            contact_info or "",                  # Phone/Email
            consult_date,                        # Consultation Date
            consult_time,                        # Consultation Time
            "30 minutes",                        # Duration
            payment_amount,                      # Payment Amount
            "UPI",                              # Payment Mode
            "TRUE" if is_split else "FALSE",   # Split Payment
            payment_details or "",              # Payment Details
            calendar_event_id or "",            # Calendar Event ID
            calendar_link or "",                # Calendar Link
            thread_id or "",                    # Thread ID
            "Confirmed",                        # Status
            notes or "",                        # Notes
        ]
        
        # Append to sheet
        range_name = f"{config['consultations_sheet']}!A:Q"
        body = {"values": [row_data]}
        
        result = service.spreadsheets().values().append(
            spreadsheetId=config['spreadsheet_id'],
            range=range_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        logger.info(
            f"✅ Consultation booking logged to Sheets: {booking_id} "
            f"for {customer_name} on {consult_date} at {consult_time}"
        )
        
        return {
            "success": True,
            "booking_id": booking_id,
            "row_number": result.get('updates', {}).get('updatedRows', 1),
        }
        
    except ValueError as e:
        # Configuration error (missing spreadsheet ID)
        logger.error(f"❌ Sheets configuration error: {e}")
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        # API or other errors
        logger.error(f"❌ Failed to log consultation booking to Sheets: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def log_product_order(
    product_type: str,
    product_name: str,
    customer_name: str,
    payment_amount: int,
    shipping_address: str,
    gotra: Optional[str] = None,
    contact_info: Optional[str] = None,
    payment_details: Optional[str] = None,
    puja_date: Optional[str] = None,
    thread_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a product/puja order to Google Sheets.
    
    This function appends a new row to the "Products" sheet with all
    order details including product type, customer info, payment, and
    shipping address.
    
    Args:
        product_type: Type of product (Kalawa, Yantra, Puja)
        product_name: Specific product name
        customer_name: Full name
        payment_amount: Amount paid in rupees
        shipping_address: Delivery address
        gotra: Family lineage (if provided)
        contact_info: Phone or email
        payment_details: Split payment breakdown
        puja_date: Date of puja/blessing
        thread_id: Session ID
        notes: Additional notes
        
    Returns:
        dict with:
            - success: bool
            - order_id: str (if success)
            - row_number: int (if success)
            - error: str (if failure)
            
    Example:
        >>> result = log_product_order(
        ...     product_type="Apamarg Jad Kalawa",
        ...     product_name="Kalawa - Blessed on Purnima",
        ...     customer_name="Priya Gupta",
        ...     payment_amount=2100,
        ...     shipping_address="123, MG Road, Delhi - 110001",
        ...     gotra="Kashyap",
        ...     contact_info="priya@example.com"
        ... )
        >>> print(result['order_id'])
        'PROD_20251006_083530'
    """
    try:
        config = get_sheets_config()
        service = get_sheets_service()
        
        # Generate order ID
        order_id = _generate_booking_id("product")
        
        # Determine if split payment
        is_split = payment_details is not None and "+" in str(payment_details)
        
        # Prepare row data (matches sheet schema)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            timestamp,                           # Timestamp
            order_id,                            # Order ID
            product_type,                        # Product Type
            product_name,                        # Product Name
            customer_name,                       # Customer Name
            gotra or "",                         # Gotra
            contact_info or "",                  # Phone/Email
            shipping_address,                    # Shipping Address
            payment_amount,                      # Payment Amount
            "UPI",                              # Payment Mode
            "TRUE" if is_split else "FALSE",   # Split Payment
            payment_details or "",              # Payment Details
            puja_date or "",                    # Puja Date
            thread_id or "",                    # Thread ID
            "Pending Blessing",                 # Order Status
            "",                                 # Dispatch Date (empty initially)
            "",                                 # Tracking ID (empty initially)
            notes or "",                        # Notes
        ]
        
        # Append to sheet
        range_name = f"{config['products_sheet']}!A:R"
        body = {"values": [row_data]}
        
        result = service.spreadsheets().values().append(
            spreadsheetId=config['spreadsheet_id'],
            range=range_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        
        logger.info(
            f"✅ Product order logged to Sheets: {order_id} "
            f"for {customer_name} - {product_type}"
        )
        
        return {
            "success": True,
            "order_id": order_id,
            "row_number": result.get('updates', {}).get('updatedRows', 1),
        }
        
    except ValueError as e:
        # Configuration error
        logger.error(f"❌ Sheets configuration error: {e}")
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        # API or other errors
        logger.error(f"❌ Failed to log product order to Sheets: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


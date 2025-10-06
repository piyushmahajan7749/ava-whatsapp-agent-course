"""Test script to diagnose calendar booking issues."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import logging
from datetime import datetime, timedelta
from ai_companion.modules.calendar.google_calendar_tools import (
    check_calendar_availability,
    book_calendar_event,
    set_payment_verified
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_calendar_booking():
    """Test calendar booking directly."""
    
    print("=" * 60)
    print("🧪 Testing Calendar Booking")
    print("=" * 60)
    print()
    
    # Generate test times (tomorrow at 11 AM IST)
    tomorrow = datetime.now() + timedelta(days=1)
    start_time = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=30)
    
    # Format in ISO with IST timezone
    start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S") + "+05:30"
    end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S") + "+05:30"
    
    print(f"📅 Test Appointment:")
    print(f"   Start: {start_time_str}")
    print(f"   End:   {end_time_str}")
    print()
    
    # Step 1: Check availability
    print("Step 1: Checking calendar availability...")
    try:
        availability_result = check_calendar_availability.invoke({
            "start_time": start_time_str,
            "end_time": end_time_str
        })
        print(f"✅ Availability check result:")
        print(f"   {availability_result}")
        print()
    except Exception as e:
        print(f"❌ Availability check failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Set payment as verified (simulate payment verification)
    print("Step 2: Simulating payment verification...")
    # Note: Without thread_id context, payment check will be skipped
    print("⚠️  Payment verification requires thread_id context")
    print("   (Will be skipped in direct tool call)")
    print()
    
    # Step 3: Book the event
    print("Step 3: Booking calendar event...")
    try:
        booking_result = book_calendar_event.invoke({
            "start_time": start_time_str,
            "end_time": end_time_str,
            "event_title": "Test Consultation - Direct Tool Call",
            "event_description": "Testing calendar booking functionality",
            "attendee_email": ""
        })
        
        print("✅ Booking result:")
        print(f"   {booking_result}")
        print()
        
        if "successfully booked" in booking_result.lower():
            print("🎉 SUCCESS! Event was created in Google Calendar")
            print("   Please check your calendar to verify")
        else:
            print("⚠️  Booking response doesn't indicate success")
            
    except Exception as e:
        print(f"❌ Booking failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    print("=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_calendar_booking()
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


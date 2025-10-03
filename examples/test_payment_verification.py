"""
Test script to demonstrate payment verification functionality.

This script shows how the payment verification system works
and provides test cases for validation.
"""

from ai_companion.modules.calendar.google_calendar_tools import (
    set_payment_verified,
    get_payment_verified,
)


def test_payment_verification():
    """Test the payment verification system."""
    print("=" * 60)
    print("Payment Verification System - Test Script")
    print("=" * 60)
    
    # Test 1: Check initial state (should be False)
    print("\n[Test 1] Initial State Check")
    thread_id = "test_user_123"
    is_verified = get_payment_verified(thread_id)
    print(f"Payment verified for {thread_id}: {is_verified}")
    assert is_verified == False, "Initial state should be False"
    print("✅ PASS: Initial state is correctly False")
    
    # Test 2: Set payment verified
    print("\n[Test 2] Setting Payment Verified")
    set_payment_verified(thread_id, True)
    is_verified = get_payment_verified(thread_id)
    print(f"Payment verified for {thread_id}: {is_verified}")
    assert is_verified == True, "Payment should be verified"
    print("✅ PASS: Payment verification set successfully")
    
    # Test 3: Different thread should still be False
    print("\n[Test 3] Different Thread Check")
    different_thread = "test_user_456"
    is_verified = get_payment_verified(different_thread)
    print(f"Payment verified for {different_thread}: {is_verified}")
    assert is_verified == False, "Different thread should be False"
    print("✅ PASS: Different threads are isolated")
    
    # Test 4: Reset payment verification
    print("\n[Test 4] Resetting Payment Verification")
    set_payment_verified(thread_id, False)
    is_verified = get_payment_verified(thread_id)
    print(f"Payment verified for {thread_id}: {is_verified}")
    assert is_verified == False, "Payment should be unverified"
    print("✅ PASS: Payment verification reset successfully")
    
    print("\n" + "=" * 60)
    print("All Tests Passed! ✅")
    print("=" * 60)


def demonstrate_workflow():
    """Demonstrate the typical workflow."""
    print("\n" + "=" * 60)
    print("Typical User Workflow Demonstration")
    print("=" * 60)
    
    thread_id = "user_whatsapp_123"
    
    print("\n📱 Step 1: User wants to book appointment")
    print("User: 'Book appointment for Oct 5 at 2pm'")
    print(f"Payment verified: {get_payment_verified(thread_id)}")
    print("❌ Tool returns: 'Payment verification required before booking'")
    
    print("\n📱 Step 2: Agent asks for payment")
    print("Agent: 'Please send payment screenshot first...'")
    
    print("\n📱 Step 3: User uploads payment screenshot")
    print("User: *uploads image* 'Here is my payment of ₹500 via GPay'")
    print("System: Detects keywords ('₹500', 'payment', 'GPay') + Image")
    set_payment_verified(thread_id, True)
    print(f"✅ Payment verified: {get_payment_verified(thread_id)}")
    
    print("\n📱 Step 4: User books appointment")
    print("User: 'Please book for Oct 5 at 2pm'")
    print(f"Payment verified: {get_payment_verified(thread_id)}")
    print("✅ Tool proceeds: 'Event successfully booked...'")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        test_payment_verification()
        demonstrate_workflow()
        print("\n🎉 Payment verification system is working correctly!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


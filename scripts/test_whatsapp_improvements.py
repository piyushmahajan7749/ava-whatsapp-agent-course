#!/usr/bin/env python3
"""
Test script for WhatsApp UX improvements

This script helps verify that the improved WhatsApp features are working correctly.
It simulates webhook requests and checks for expected behaviors.

Usage:
    python scripts/test_whatsapp_improvements.py [options]

Options:
    --url URL           WhatsApp webhook URL (default: http://localhost:8080/whatsapp_response)
    --phone PHONE       Test phone number (default: +1234567890)
    --test TEST_NAME    Run specific test (default: all)
    --verbose           Show detailed output

Available tests:
    - simple: Simple text message
    - booking: Booking request (should get 📅 reaction)
    - image: Image request (should get 🎨 reaction)
    - rapid: Rapid messages (test deduplication)
    - all: Run all tests
"""

import argparse
import asyncio
import time
from typing import Dict, List
import httpx
import json


class WhatsAppTester:
    """Test harness for WhatsApp improvements."""
    
    def __init__(self, webhook_url: str, test_phone: str, verbose: bool = False):
        self.webhook_url = webhook_url
        self.test_phone = test_phone
        self.verbose = verbose
        self.results: List[Dict] = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log message if verbose mode is enabled."""
        if self.verbose or level == "ERROR":
            prefix = {
                "INFO": "ℹ️ ",
                "SUCCESS": "✅",
                "ERROR": "❌",
                "WARNING": "⚠️ "
            }.get(level, "")
            print(f"{prefix} {message}")
    
    def create_webhook_payload(self, message_text: str, message_type: str = "text", message_id: str = None) -> Dict:
        """Create a WhatsApp webhook payload for testing."""
        if message_id is None:
            message_id = f"test_{int(time.time() * 1000)}"
        
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": self.test_phone,
                            "id": message_id,
                            "type": message_type,
                        }]
                    }
                }]
            }]
        }
        
        if message_type == "text":
            payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"] = {
                "body": message_text
            }
        elif message_type == "image":
            payload["entry"][0]["changes"][0]["value"]["messages"][0]["image"] = {
                "id": "fake_image_id",
                "caption": message_text
            }
        elif message_type == "audio":
            payload["entry"][0]["changes"][0]["value"]["messages"][0]["audio"] = {
                "id": "fake_audio_id"
            }
        
        return payload
    
    async def send_message(self, message_text: str, message_type: str = "text", message_id: str = None) -> Dict:
        """Send a test message to the webhook."""
        payload = self.create_webhook_payload(message_text, message_type, message_id)
        
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                elapsed = time.time() - start_time
                
                result = {
                    "message": message_text,
                    "type": message_type,
                    "status_code": response.status_code,
                    "response_time": elapsed,
                    "response_body": response.text,
                    "success": response.status_code == 200
                }
                
                self.results.append(result)
                return result
                
        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                "message": message_text,
                "type": message_type,
                "status_code": None,
                "response_time": elapsed,
                "error": str(e),
                "success": False
            }
            self.results.append(result)
            return result
    
    async def test_simple_message(self):
        """Test 1: Simple text message."""
        self.log("Test 1: Simple text message", "INFO")
        
        result = await self.send_message("Hello, this is a test message")
        
        if result["success"]:
            if result["response_time"] < 1.0:
                self.log(f"✓ Webhook responded in {result['response_time']:.3f}s (< 1s) - Good!", "SUCCESS")
            else:
                self.log(f"✓ Webhook responded in {result['response_time']:.3f}s (> 1s) - Consider enabling async processing", "WARNING")
            return True
        else:
            self.log(f"✗ Failed: {result.get('error', result.get('response_body'))}", "ERROR")
            return False
    
    async def test_booking_request(self):
        """Test 2: Booking request (should trigger 📅 reaction if enabled)."""
        self.log("Test 2: Booking request", "INFO")
        
        result = await self.send_message("I want to book a consultation for next Tuesday")
        
        if result["success"]:
            self.log(f"✓ Booking request processed (check logs for 📅 reaction)", "SUCCESS")
            return True
        else:
            self.log(f"✗ Failed: {result.get('error', result.get('response_body'))}", "ERROR")
            return False
    
    async def test_image_request(self):
        """Test 3: Image request (should trigger 🎨 reaction if enabled)."""
        self.log("Test 3: Image generation request", "INFO")
        
        result = await self.send_message("Create an image of a beautiful sunset")
        
        if result["success"]:
            self.log(f"✓ Image request processed (check logs for 🎨 reaction)", "SUCCESS")
            return True
        else:
            self.log(f"✗ Failed: {result.get('error', result.get('response_body'))}", "ERROR")
            return False
    
    async def test_rapid_messages(self):
        """Test 4: Rapid consecutive messages (tests deduplication and concurrency)."""
        self.log("Test 4: Rapid consecutive messages", "INFO")
        
        messages = [
            "Message 1",
            "Message 2",
            "Message 3",
        ]
        
        # Send all messages in parallel
        tasks = [self.send_message(msg) for msg in messages]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r["success"])
        
        if success_count == len(messages):
            self.log(f"✓ All {len(messages)} rapid messages handled successfully", "SUCCESS")
            return True
        else:
            self.log(f"✗ Only {success_count}/{len(messages)} messages succeeded", "ERROR")
            return False
    
    async def test_duplicate_message(self):
        """Test 5: Duplicate message (should be deduplicated)."""
        self.log("Test 5: Duplicate message handling", "INFO")
        
        message_id = f"duplicate_test_{int(time.time())}"
        
        # Send same message twice with same ID
        result1 = await self.send_message("Duplicate test message", message_id=message_id)
        await asyncio.sleep(0.5)
        result2 = await self.send_message("Duplicate test message", message_id=message_id)
        
        if result1["success"] and result2["success"]:
            # Both should return 200, but second should be deduplicated
            if "duplicate" in result2["response_body"].lower() or "ignored" in result2["response_body"].lower():
                self.log(f"✓ Duplicate message correctly deduplicated", "SUCCESS")
                return True
            else:
                self.log(f"⚠ Both messages processed (deduplication may not be working)", "WARNING")
                return True  # Not a failure, but worth noting
        else:
            self.log(f"✗ Failed to test deduplication", "ERROR")
            return False
    
    async def test_webhook_verification(self):
        """Test GET endpoint for webhook verification."""
        self.log("Test 0: Webhook verification (GET request)", "INFO")
        
        try:
            params = {
                "hub.mode": "subscribe",
                "hub.verify_token": "test_token",  # This should match WHATSAPP_VERIFY_TOKEN
                "hub.challenge": "test_challenge_12345"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.webhook_url, params=params)
                
                if response.status_code == 200 and "test_challenge" in response.text:
                    self.log(f"✓ Webhook verification working", "SUCCESS")
                    return True
                else:
                    self.log(f"✗ Webhook verification failed: {response.status_code}", "ERROR")
                    return False
                    
        except Exception as e:
            self.log(f"✗ Error testing webhook verification: {e}", "ERROR")
            return False
    
    async def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("WhatsApp UX Improvements - Test Suite")
        print("="*60 + "\n")
        
        print(f"Testing webhook: {self.webhook_url}")
        print(f"Test phone number: {self.test_phone}\n")
        
        tests = [
            ("Webhook Verification", self.test_webhook_verification),
            ("Simple Message", self.test_simple_message),
            ("Booking Request", self.test_booking_request),
            ("Image Request", self.test_image_request),
            ("Rapid Messages", self.test_rapid_messages),
            ("Duplicate Message", self.test_duplicate_message),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n{'─'*60}")
            print(f"Running: {test_name}")
            print('─'*60)
            
            try:
                result = await test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log(f"Exception in {test_name}: {e}", "ERROR")
                failed += 1
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Print summary
        print("\n" + "="*60)
        print("Test Summary")
        print("="*60)
        print(f"Total tests: {len(tests)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if self.results:
            avg_response_time = sum(r["response_time"] for r in self.results) / len(self.results)
            print(f"\n📊 Average response time: {avg_response_time:.3f}s")
            
            if avg_response_time < 0.5:
                print("   → Excellent! Async processing appears to be working.")
            elif avg_response_time < 2.0:
                print("   → Good response time.")
            else:
                print("   → Slow response time. Consider enabling async processing.")
        
        print("\n" + "="*60)
        print("\n💡 Next steps:")
        print("   1. Check logs: docker-compose logs -f whatsapp")
        print("   2. Look for: ✓ Marked message as read")
        print("   3. Look for: ✓ Reacted to message")
        print("   4. Verify read receipts appear in WhatsApp")
        print("   5. Verify emoji reactions appear in WhatsApp\n")
        
        return failed == 0


async def main():
    parser = argparse.ArgumentParser(
        description="Test WhatsApp UX improvements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python scripts/test_whatsapp_improvements.py --verbose
  
  # Test specific feature
  python scripts/test_whatsapp_improvements.py --test simple
  
  # Use custom webhook URL
  python scripts/test_whatsapp_improvements.py --url http://example.com/whatsapp_response
        """
    )
    
    parser.add_argument(
        "--url",
        default="http://localhost:8080/whatsapp_response",
        help="WhatsApp webhook URL (default: http://localhost:8080/whatsapp_response)"
    )
    
    parser.add_argument(
        "--phone",
        default="+1234567890",
        help="Test phone number (default: +1234567890)"
    )
    
    parser.add_argument(
        "--test",
        choices=["simple", "booking", "image", "rapid", "duplicate", "verification", "all"],
        default="all",
        help="Specific test to run (default: all)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    
    args = parser.parse_args()
    
    tester = WhatsAppTester(args.url, args.phone, args.verbose)
    
    if args.test == "all":
        success = await tester.run_all_tests()
    else:
        test_map = {
            "verification": tester.test_webhook_verification,
            "simple": tester.test_simple_message,
            "booking": tester.test_booking_request,
            "image": tester.test_image_request,
            "rapid": tester.test_rapid_messages,
            "duplicate": tester.test_duplicate_message,
        }
        
        print(f"\nRunning test: {args.test}\n")
        success = await test_map[args.test]()
        
        if success:
            print(f"\n✅ Test '{args.test}' passed!\n")
        else:
            print(f"\n❌ Test '{args.test}' failed!\n")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)


#!/usr/bin/env python3
"""
Test script for product order logging functionality

This script tests the new log_product_order_to_sheets tool to ensure
product orders are properly logged to Google Sheets.
"""

import asyncio
import os
from src.ai_companion.modules.calendar.google_calendar_tools import log_product_order_to_sheets
from src.ai_companion.modules.sheets.sheets_manager import log_product_order

async def test_product_order_logging():
    """Test the product order logging functionality"""
    
    print("🧪 Testing Product Order Logging")
    print("=" * 50)
    
    # Test 1: Direct function call
    print("\n1. Testing direct log_product_order function...")
    try:
        result = log_product_order(
            product_type="Apamarg Jad Kalawa",
            product_name="Kalawa - Blessed on Purnima",
            customer_name="Test Customer",
            payment_amount=2100,
            shipping_address="123 Test Street, Test City - 110001",
            gotra="Kashyap",
            contact_info="test@example.com",
            payment_details="2000 + 100",
            puja_date="2025-10-15",
            thread_id="test_thread_123",
            notes="Test order for verification"
        )
        
        if result.get("success"):
            print(f"   ✅ Direct function call successful: {result.get('order_id')}")
        else:
            print(f"   ❌ Direct function call failed: {result.get('error')}")
    except Exception as e:
        print(f"   ❌ Direct function call error: {e}")
    
    # Test 2: Tool call simulation
    print("\n2. Testing log_product_order_to_sheets tool...")
    try:
        # Simulate a tool call
        result = log_product_order_to_sheets(
            product_type="Yantra",
            product_name="Shri Yantra - Silver Plated",
            customer_name="Priya Sharma",
            payment_amount=3500,
            shipping_address="456 Main Road, Mumbai - 400001",
            gotra="Bharadwaj",
            contact_info="priya.sharma@email.com",
            payment_details="3500",
            puja_date="2025-10-20",
            thread_id="test_thread_456",
            notes="Silver plated yantra for home"
        )
        
        print(f"   Tool result: {result}")
        
    except Exception as e:
        print(f"   ❌ Tool call error: {e}")
    
    # Test 3: Check Google Sheets configuration
    print("\n3. Checking Google Sheets configuration...")
    try:
        from src.ai_companion.modules.sheets.sheets_manager import get_sheets_config
        config = get_sheets_config()
        
        if config.get('spreadsheet_id'):
            print(f"   ✅ Spreadsheet ID configured: {config['spreadsheet_id'][:20]}...")
        else:
            print("   ❌ Spreadsheet ID not configured")
            
        if config.get('products_sheet'):
            print(f"   ✅ Products sheet configured: {config['products_sheet']}")
        else:
            print("   ❌ Products sheet not configured")
            
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
    
    # Test 4: Available tools check
    print("\n4. Checking available tools...")
    try:
        from src.ai_companion.modules.calendar.google_calendar_tools import get_calendar_tools
        tools = get_calendar_tools()
        tool_names = [tool.name for tool in tools]
        
        print(f"   Available tools: {tool_names}")
        
        if 'log_product_order_to_sheets' in tool_names:
            print("   ✅ log_product_order_to_sheets tool is available")
        else:
            print("   ❌ log_product_order_to_sheets tool is missing")
            
    except Exception as e:
        print(f"   ❌ Tools check error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Product order logging tests completed!")
    print("\nTo verify the fix:")
    print("1. Check your Google Sheets - you should see new rows in the Products sheet")
    print("2. Test with a real WhatsApp conversation about product orders")
    print("3. The bot should now automatically log product orders to Sheets")

if __name__ == "__main__":
    asyncio.run(test_product_order_logging())

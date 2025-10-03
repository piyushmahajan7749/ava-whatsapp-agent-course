#!/usr/bin/env python3
"""
Setup script for Google Calendar integration.

This script:
1. Verifies credentials.json exists
2. Installs required dependencies
3. Tests the OAuth flow
4. Verifies calendar access
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def check_credentials():
    """Check if credentials.json exists."""
    credentials_path = project_root / "credentials.json"
    if not credentials_path.exists():
        print("❌ ERROR: credentials.json not found!")
        print("\nPlease follow these steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing")
        print("3. Enable Google Calendar API")
        print("4. Create OAuth 2.0 credentials")
        print("5. Download credentials.json")
        print(f"6. Place it at: {credentials_path}")
        return False
    
    print(f"✅ Found credentials.json at {credentials_path}")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    # Map of package names to their import names
    required_packages = {
        "google-auth": "google.auth",
        "google-auth-oauthlib": "google_auth_oauthlib",
        "google-auth-httplib2": "google_auth_httplib2",
        "google-api-python-client": "googleapiclient"
    }
    
    missing_packages = []
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✅ {package_name} installed")
        except ImportError:
            print(f"❌ {package_name} not installed")
            missing_packages.append(package_name)
    
    if missing_packages:
        print("\n⚠️  Missing packages detected.")
        print("\nTo install, run:")
        print("  uv sync")
        print("\nOr manually install:")
        print(f"  pip install {' '.join(missing_packages)}")
        return False
    
    return True


def test_authentication():
    """Test OAuth authentication flow."""
    print("\n" + "="*60)
    print("Testing Google Calendar Authentication")
    print("="*60)
    
    try:
        from ai_companion.modules.calendar.auth import get_calendar_service
        
        print("\n📅 Initializing Google Calendar service...")
        print("⚠️  This will open your browser for OAuth authorization")
        print("   (only needed on first run)")
        
        service = get_calendar_service()
        
        # Test by listing calendars
        print("\n✅ Authentication successful!")
        print("\n📋 Your calendars:")
        
        calendars_result = service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        
        if calendars:
            for calendar in calendars[:5]:  # Show first 5
                print(f"  - {calendar['summary']}")
            if len(calendars) > 5:
                print(f"  ... and {len(calendars) - 5} more")
        else:
            print("  No calendars found")
        
        return True
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_calendar_tools():
    """Test the calendar tools."""
    print("\n" + "="*60)
    print("Testing Calendar Tools")
    print("="*60)
    
    try:
        from ai_companion.modules.calendar.google_calendar_tools import (
            check_calendar_availability,
            book_calendar_event
        )
        from datetime import datetime, timedelta
        
        # Test availability check
        print("\n🔍 Testing availability check...")
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        result = check_calendar_availability.invoke({
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        })
        print(f"\nResult: {result}")
        
        print("\n✅ Calendar tools are working!")
        print("\n⚠️  Note: We didn't test event booking to avoid creating test events.")
        print("   To test booking, use the test script: python examples/test_tool_calling.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all setup checks."""
    print("="*60)
    print("Google Calendar Integration Setup")
    print("="*60)
    
    print("\n📋 Step 1: Checking credentials...")
    if not check_credentials():
        print("\n❌ Setup failed: credentials.json not found")
        return 1
    
    print("\n📦 Step 2: Checking dependencies...")
    if not check_dependencies():
        print("\n❌ Setup failed: missing dependencies")
        print("\nRun: uv sync")
        print("Then run this script again.")
        return 1
    
    print("\n🔐 Step 3: Testing authentication...")
    if not test_authentication():
        print("\n❌ Setup failed: authentication error")
        return 1
    
    print("\n🛠️  Step 4: Testing calendar tools...")
    if not test_calendar_tools():
        print("\n❌ Setup failed: tool error")
        return 1
    
    print("\n" + "="*60)
    print("✅ Setup Complete!")
    print("="*60)
    print("\nYour Google Calendar integration is ready to use!")
    print("\nNext steps:")
    print("1. Run your AI companion: chainlit run src/ai_companion/interfaces/chainlit/app.py")
    print("2. Try asking: 'Am I available tomorrow at 2pm?'")
    print("3. Or book an event: 'Book a meeting for tomorrow at 3pm'")
    print("\nThe token.json file has been saved and will be used for future requests.")
    print("You won't need to authorize again unless you delete token.json.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


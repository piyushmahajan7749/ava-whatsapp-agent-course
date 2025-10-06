"""Setup Google Sheets with proper headers and formatting for booking logs."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_companion.modules.calendar.auth import get_sheets_service
from ai_companion.modules.sheets.sheets_manager import get_sheets_config


def setup_consultations_sheet(service, spreadsheet_id: str, sheet_id: int = 0):
    """
    Setup Consultations sheet with headers and formatting.
    
    Args:
        service: Authenticated Sheets API service
        spreadsheet_id: ID of the spreadsheet
        sheet_id: ID of the sheet tab (default: 0 for first sheet)
    """
    print("📋 Setting up Consultations sheet...")
    
    # Define headers
    headers = [
        ["Timestamp", "Booking ID", "Customer Name", "Date of Birth", "Phone/Email",
         "Consultation Date", "Consultation Time", "Duration", "Payment Amount", 
         "Payment Mode", "Split Payment", "Payment Details", "Calendar Event ID", 
         "Calendar Link", "Thread ID", "Status", "Notes"]
    ]
    
    # Write headers to first row
    range_name = "Consultations!A1:Q1"
    body = {"values": headers}
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()
    
    # Format headers: bold text + gray background + freeze first row
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True, "fontSize": 10},
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)"
            }
        },
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        },
        # Auto-resize columns
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 17
                }
            }
        }
    ]
    
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()
    
    print("✅ Consultations sheet setup complete!")


def setup_products_sheet(service, spreadsheet_id: str, sheet_id: int = 1):
    """
    Setup Products sheet with headers and formatting.
    
    Args:
        service: Authenticated Sheets API service
        spreadsheet_id: ID of the spreadsheet
        sheet_id: ID of the sheet tab (default: 1 for second sheet)
    """
    print("📋 Setting up Products sheet...")
    
    # Define headers
    headers = [
        ["Timestamp", "Order ID", "Product Type", "Product Name", "Customer Name",
         "Gotra", "Phone/Email", "Shipping Address", "Payment Amount", "Payment Mode",
         "Split Payment", "Payment Details", "Puja Date", "Thread ID", "Order Status",
         "Dispatch Date", "Tracking ID", "Notes"]
    ]
    
    # Write headers to first row
    range_name = "Products!A1:R1"
    body = {"values": headers}
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()
    
    # Format headers: bold text + gray background + freeze first row
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True, "fontSize": 10},
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)"
            }
        },
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        },
        # Auto-resize columns
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 18
                }
            }
        }
    ]
    
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests}
    ).execute()
    
    print("✅ Products sheet setup complete!")


def get_sheet_ids(service, spreadsheet_id: str) -> dict:
    """
    Get sheet IDs by name.
    
    Returns:
        dict mapping sheet names to their IDs
    """
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = spreadsheet.get('sheets', [])
    
    sheet_ids = {}
    for sheet in sheets:
        properties = sheet.get('properties', {})
        sheet_name = properties.get('title')
        sheet_id = properties.get('sheetId')
        if sheet_name and sheet_id is not None:
            sheet_ids[sheet_name] = sheet_id
    
    return sheet_ids


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("🔧 Google Sheets Setup for Upaai Bookings")
        print("=" * 60)
        print()
        
        # Get configuration
        print("📝 Loading configuration...")
        config = get_sheets_config()
        spreadsheet_id = config['spreadsheet_id']
        
        print(f"✅ Spreadsheet ID: {spreadsheet_id}")
        print()
        
        # Get authenticated service
        print("🔐 Authenticating with Google Sheets API...")
        service = get_sheets_service()
        print("✅ Authentication successful!")
        print()
        
        # Get sheet IDs
        print("🔍 Finding sheet IDs...")
        sheet_ids = get_sheet_ids(service, spreadsheet_id)
        print(f"Found sheets: {list(sheet_ids.keys())}")
        print()
        
        # Setup Consultations sheet
        if 'Consultations' in sheet_ids:
            setup_consultations_sheet(service, spreadsheet_id, sheet_ids['Consultations'])
        else:
            print("⚠️  'Consultations' sheet not found. Please create it first.")
            print("   1. Open your spreadsheet")
            print("   2. Create a sheet named 'Consultations'")
            print("   3. Run this script again")
            print()
        
        # Setup Products sheet
        if 'Products' in sheet_ids:
            setup_products_sheet(service, spreadsheet_id, sheet_ids['Products'])
        else:
            print("⚠️  'Products' sheet not found. Please create it first.")
            print("   1. Open your spreadsheet")
            print("   2. Create a sheet named 'Products'")
            print("   3. Run this script again")
            print()
        
        print("=" * 60)
        print("✅ Google Sheets setup complete!")
        print("=" * 60)
        print()
        print(f"📊 View your spreadsheet:")
        print(f"   https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
        print()
        print("💡 Next steps:")
        print("   1. Verify the headers look correct")
        print("   2. Test booking a consultation to see data appear")
        print("   3. Share the sheet with your team members")
        print()
        
    except ValueError as e:
        print()
        print("❌ Configuration Error:")
        print(f"   {e}")
        print()
        print("💡 To fix this:")
        print("   1. Create a new Google Sheet")
        print("   2. Name it 'Upaai Bookings'")
        print("   3. Create two sheets: 'Consultations' and 'Products'")
        print("   4. Copy the Spreadsheet ID from the URL")
        print("      Example: https://docs.google.com/spreadsheets/d/{ID}/edit")
        print("   5. Add to your .env file:")
        print("      GOOGLE_SHEETS_BOOKING_ID='your_spreadsheet_id_here'")
        print()
        sys.exit(1)
        
    except FileNotFoundError as e:
        print()
        print("❌ Authentication Error:")
        print(f"   {e}")
        print()
        print("💡 To fix this:")
        print("   1. Ensure credentials.json is in your project root")
        print("   2. If token.json exists, delete it to re-authenticate")
        print("   3. Run this script again")
        print()
        sys.exit(1)
        
    except Exception as e:
        print()
        print("❌ Unexpected Error:")
        print(f"   {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


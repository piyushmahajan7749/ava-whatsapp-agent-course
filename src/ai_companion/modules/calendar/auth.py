"""Google Calendar OAuth authentication helper."""

import os
import logging
from pathlib import Path
from functools import lru_cache

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Scopes required for calendar operations
SCOPES = ['https://www.googleapis.com/auth/calendar']

# File paths - try multiple locations
def _get_project_root():
    """Find project root by looking for pyproject.toml or credentials.json"""
    # Start from this file's location
    current = Path(__file__).resolve()
    
    # Try going up from src/ai_companion/modules/calendar/auth.py
    # Should be: auth.py -> calendar -> modules -> ai_companion -> src -> project_root
    possible_root = current.parent.parent.parent.parent.parent
    
    # Verify by checking for pyproject.toml
    if (possible_root / 'pyproject.toml').exists():
        return possible_root
    
    # Fallback: use current working directory
    cwd = Path.cwd()
    if (cwd / 'pyproject.toml').exists():
        return cwd
    
    # Last resort: check parent of cwd
    if (cwd.parent / 'pyproject.toml').exists():
        return cwd.parent
    
    # Default to possible_root
    return possible_root

PROJECT_ROOT = _get_project_root()
CREDENTIALS_FILE = PROJECT_ROOT / 'credentials.json'
TOKEN_FILE = PROJECT_ROOT / 'token.json'

logger.debug(f"Project root resolved to: {PROJECT_ROOT}")


@lru_cache(maxsize=1)
def get_calendar_service():
    """
    Authenticate and return Google Calendar service.
    
    This function handles OAuth 2.0 authentication:
    1. Checks if token.json exists (previous auth)
    2. If token is expired, refreshes it
    3. If no token, initiates OAuth flow
    4. Returns authenticated Calendar API service
    
    Returns:
        googleapiclient.discovery.Resource: Authenticated Calendar API service
        
    Raises:
        FileNotFoundError: If credentials.json is not found
        Exception: If authentication fails
    """
    creds = None
    
    # Check if we have previously saved credentials
    if TOKEN_FILE.exists():
        logger.info("Loading existing token from token.json")
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load token.json: {e}")
            creds = None
    
    # If credentials are invalid or don't exist, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                # Delete invalid token and re-authenticate
                if TOKEN_FILE.exists():
                    TOKEN_FILE.unlink()
                creds = None
        
        if not creds:
            # Check if credentials.json exists
            if not CREDENTIALS_FILE.exists():
                logger.error(f"Looking for credentials.json at: {CREDENTIALS_FILE}")
                logger.error(f"Project root resolved to: {PROJECT_ROOT}")
                logger.error(f"Current working directory: {Path.cwd()}")
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    f"Please download it from Google Cloud Console and place it in the project root ({PROJECT_ROOT})."
                )
            
            logger.info("Starting OAuth flow for first-time authentication")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), 
                SCOPES
            )
            
            # Run local server for OAuth flow
            # This will open browser for user to authorize
            creds = flow.run_local_server(port=0)
            
            logger.info("Authentication successful")
        
        # Save the credentials for future use
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            logger.info(f"Token saved to {TOKEN_FILE}")
    
    # Build and return the service
    service = build('calendar', 'v3', credentials=creds)
    logger.info("Google Calendar service initialized successfully")
    return service


def clear_token():
    """
    Clear stored authentication token.
    
    Useful for:
    - Switching Google accounts
    - Fixing authentication issues
    - Testing OAuth flow
    """
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        logger.info("Token cleared. Next API call will re-authenticate.")
        # Clear the cache
        get_calendar_service.cache_clear()
    else:
        logger.info("No token file to clear.")


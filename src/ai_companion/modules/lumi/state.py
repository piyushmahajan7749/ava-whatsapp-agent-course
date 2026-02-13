"""
Lumi onboarding state model and persistence.

Stores user onboarding progress and captured data in SQLite.
"""

import json
import logging
import sqlite3
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from ai_companion.settings import settings

logger = logging.getLogger(__name__)


class OnboardingStage(str, Enum):
    """Stages in the Lumi onboarding flow."""

    # Main flow stages
    WELCOME = "welcome"  # Stage 1
    DEMOGRAPHICS = "demographics"  # Stage 2
    STORY = "story"  # Stage 3
    THERAPY_HISTORY = "therapy_history"  # Stage 4
    CARE_PREFERENCES = "care_preferences"  # Stage 5
    MEDICATION = "medication"  # Stage 6
    CONCERNS = "concerns"  # Stage 7
    LANGUAGE = "language"  # Stage 8
    THERAPIST_STYLE = "therapist_style"  # Stage 9
    GENDER_PREFERENCE = "gender_preference"  # Stage 10
    PERSONAL_CONTEXT = "personal_context"  # Stage 11 (relationship, DOB, city)
    PROCESSING = "processing"  # Stage 12
    MATCH_REVEAL = "match_reveal"  # Stage 13
    BOOKING = "booking"  # Stage 14
    CONFIRMED = "confirmed"  # Stage 15

    # Special states
    HUMAN_HANDOFF = "human_handoff"
    ARCHIVED = "archived"

    # Sub-stages for multi-part questions
    PERSONAL_DOB = "personal_dob"
    PERSONAL_CITY = "personal_city"
    ALTERNATIVE_THERAPISTS = "alternative_therapists"

    # Warm-up conversation before route selection
    WARMUP = "warmup"
    WARMUP_2 = "warmup_2"

    # Route selection after welcome
    ROUTE_SELECT = "route_select"

    # Browse experts (stays open for questions)
    BROWSE_EXPERTS = "browse_experts"

    # Consultation booking flow
    CONSULTATION_INTRO = "consultation_intro"
    CONSULTATION_DATE = "consultation_date"
    CONSULTATION_TIME_SECTION = "consultation_time_section"  # Morning/Afternoon/Evening picker
    CONSULTATION_TIME = "consultation_time"
    CONSULTATION_CONFIRMED = "consultation_confirmed"

    # Preferences collected terminal (Lumi flow without matching)
    PREFERENCES_COLLECTED = "preferences_collected"


class LumiUserState(BaseModel):
    """User state for Lumi onboarding flow."""

    phone_number: str
    stage: OnboardingStage = OnboardingStage.WELCOME

    # Captured data - Stage 2: Demographics
    age: Optional[int] = None
    gender: Optional[str] = None

    # Stage 3: Story
    story_text: Optional[str] = None

    # Stage 4: Therapy history
    therapy_history: Optional[str] = None  # "new", "didnt_stick", "helped"

    # Stage 5: Care preferences
    care_preference: Optional[str] = None  # "full_care", "just_therapy", "not_sure"

    # Stage 6: Medication
    on_medication: Optional[bool] = None
    medications: Optional[str] = None

    # Stage 7: Concerns (multi-select)
    concerns: List[str] = Field(default_factory=list)

    # Stage 8: Language
    language: Optional[str] = None

    # Stage 9: Therapist style (multi-select)
    therapist_style: List[str] = Field(default_factory=list)

    # Stage 10: Gender preference
    therapist_gender_pref: Optional[str] = None  # "man", "woman", "flexible"

    # Stage 11: Personal context
    relationship_status: Optional[str] = None
    dob: Optional[str] = None  # DD/MM/YYYY format
    city: Optional[str] = None

    # Flags for matching
    queer_affirming_flag: bool = False
    trauma_flag: bool = False
    complex_psychiatric_flag: bool = False

    # Friction tracking
    friction_detected_count: int = 0
    short_answer_count: int = 0

    # Matching results
    matched_therapist_id: Optional[str] = None
    alternative_therapist_ids: List[str] = Field(default_factory=list)
    therapist_options_shown_count: int = 0

    # User acknowledged consent
    consent_acknowledged: bool = False

    # Timing
    last_message_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)

    # Nudge tracking
    nudge_1_sent: bool = False
    nudge_2_sent: bool = False

    # Handoff context
    handoff_reason: Optional[str] = None

    # Route selection
    selected_route: Optional[str] = None  # "browse_experts", "consultation", "lumi_flow"
    browse_messages_remaining: int = 5

    # Consultation booking
    consultation_date: Optional[str] = None  # YYYY-MM-DD
    consultation_time: Optional[str] = None  # HH:MM
    available_slots: List[str] = Field(default_factory=list)  # Temp storage during booking

    # Conversation history for LLM context
    conversation_history: List[dict] = Field(default_factory=list)

    class Config:
        use_enum_values = True


_resolved_db_path: str | None = None


def _get_db_path() -> str:
    """Get the database path, with fallback for local development. Caches result."""
    global _resolved_db_path
    if _resolved_db_path is not None:
        return _resolved_db_path

    import os

    primary_path = settings.SHORT_TERM_MEMORY_DB_PATH
    alternative_path = "short_term_memory/memory.db"

    # Check if primary path exists or can be created
    if os.path.exists(primary_path):
        _resolved_db_path = primary_path
    elif os.path.exists(os.path.dirname(primary_path)):
        _resolved_db_path = primary_path
    elif os.path.exists(alternative_path) or os.path.exists(os.path.dirname(alternative_path)):
        _resolved_db_path = alternative_path
    else:
        os.makedirs(os.path.dirname(alternative_path), exist_ok=True)
        _resolved_db_path = alternative_path

    logger.info(f"[LUMI_STATE] DB path: {_resolved_db_path}")
    return _resolved_db_path


def _get_db_connection() -> sqlite3.Connection:
    """Get SQLite database connection."""
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # DELETE mode is safer on network filesystems (Azure Files SMB doesn't support WAL shared memory)
    conn.execute("PRAGMA journal_mode = DELETE")
    # Retry for up to 5 seconds if another connection holds a lock
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _ensure_table_exists():
    """Create the lumi_user_state table if it doesn't exist."""
    conn = _get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lumi_user_state (
                phone_number TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                stage TEXT NOT NULL,
                last_message_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """
        )
        conn.commit()
        logger.debug("[LUMI_STATE] Table OK")
    finally:
        conn.close()


def get_user_state(phone_number: str) -> Optional[LumiUserState]:
    """
    Get user state from database.

    Args:
        phone_number: User's phone number (E.164 without +)

    Returns:
        LumiUserState if found, None otherwise
    """
    _ensure_table_exists()
    conn = _get_db_connection()
    try:
        cursor = conn.execute(
            "SELECT state_json FROM lumi_user_state WHERE phone_number = ?",
            (phone_number,),
        )
        row = cursor.fetchone()

        if row:
            state_data = json.loads(row["state_json"])
            return LumiUserState(**state_data)

        return None
    except Exception as e:
        logger.error(f"[LUMI_STATE] Error getting state for {phone_number}: {e}")
        return None
    finally:
        conn.close()


def save_user_state(state: LumiUserState) -> bool:
    """
    Save user state to database.

    Args:
        state: LumiUserState to save

    Returns:
        True if saved successfully
    """
    _ensure_table_exists()
    conn = _get_db_connection()
    try:
        state_json = state.model_dump_json()
        conn.execute(
            """
            INSERT OR REPLACE INTO lumi_user_state
            (phone_number, state_json, stage, last_message_at, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                state.phone_number,
                state_json,
                state.stage,
                state.last_message_at.isoformat(),
                state.created_at.isoformat(),
            ),
        )
        conn.commit()
        logger.debug(f"[LUMI_STATE] Saved state for {state.phone_number}: stage={state.stage}")
        return True
    except Exception as e:
        logger.error(f"[LUMI_STATE] Error saving state for {state.phone_number}: {e}")
        return False
    finally:
        conn.close()


def delete_user_state(phone_number: str) -> bool:
    """
    Delete user state from database.

    Args:
        phone_number: User's phone number

    Returns:
        True if deleted successfully
    """
    _ensure_table_exists()
    conn = _get_db_connection()
    try:
        conn.execute(
            "DELETE FROM lumi_user_state WHERE phone_number = ?",
            (phone_number,),
        )
        conn.commit()
        logger.info(f"[LUMI_STATE] Deleted state for {phone_number}")
        return True
    except Exception as e:
        logger.error(f"[LUMI_STATE] Error deleting state for {phone_number}: {e}")
        return False
    finally:
        conn.close()


def get_stale_conversations(hours: int) -> List[LumiUserState]:
    """
    Get conversations that haven't had activity in the specified hours.

    Args:
        hours: Number of hours of inactivity

    Returns:
        List of stale user states
    """
    _ensure_table_exists()
    conn = _get_db_connection()
    try:
        cutoff = datetime.now().timestamp() - (hours * 3600)
        cursor = conn.execute(
            """
            SELECT state_json FROM lumi_user_state
            WHERE stage NOT IN ('confirmed', 'human_handoff', 'archived')
            AND datetime(last_message_at) < datetime(?, 'unixepoch')
        """,
            (cutoff,),
        )

        states = []
        for row in cursor.fetchall():
            state_data = json.loads(row["state_json"])
            states.append(LumiUserState(**state_data))

        return states
    except Exception as e:
        logger.error(f"[LUMI_STATE] Error getting stale conversations: {e}")
        return []
    finally:
        conn.close()


def clear_all_user_states() -> int:
    """
    Delete ALL user states from the database. Use for a fresh start.

    Returns:
        Number of conversations deleted.
    """
    _ensure_table_exists()
    conn = _get_db_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM lumi_user_state")
        count = cursor.fetchone()[0]
        conn.execute("DELETE FROM lumi_user_state")
        conn.commit()
        logger.info(f"[LUMI_STATE] Cleared all user states ({count} conversations)")
        return count
    except Exception as e:
        logger.error(f"[LUMI_STATE] Error clearing all states: {e}")
        return 0
    finally:
        conn.close()

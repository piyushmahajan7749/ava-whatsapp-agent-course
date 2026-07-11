from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Get the project root directory (3 levels up from this file: src/ai_companion/settings.py -> project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), 
        extra="ignore", 
        env_file_encoding="utf-8"
    )

    # Groq is used for voice-note transcription; the rest are legacy saarthi
    # integrations kept optional so the ANGC branch can boot without them.
    GROQ_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    TOGETHER_API_KEY: str = ""
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_API_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str
    AZURE_OPENAI_VISION_DEPLOYMENT: str

    QDRANT_API_KEY: str | None = None
    QDRANT_URL: str = ""
    QDRANT_PORT: str = "6333"
    QDRANT_HOST: str | None = None

    TEXT_MODEL_NAME: str = "gpt-5-chat"
    SMALL_TEXT_MODEL_NAME: str = "gpt-5-mini"# Azure OpenAI Vision deployment name
    STT_MODEL_NAME: str = "whisper-large-v3-turbo"
    TTS_MODEL_NAME: str = "eleven_flash_v2_5"
    TTI_MODEL_NAME: str = "black-forest-labs/FLUX.1-schnell-Free"

    MEMORY_TOP_K: int = 3
    ROUTER_MESSAGES_TO_ANALYZE: int = 3
    TOTAL_MESSAGES_SUMMARY_TRIGGER: int = 20
    TOTAL_MESSAGES_AFTER_SUMMARY: int = 5

    SHORT_TERM_MEMORY_DB_PATH: str = "/app/data/memory.db"

    # Optional: path to a UPI QR image to share on request
    UPI_QR_IMAGE_PATH: str | None = "img/QrCode.jpeg"
    
    # Google Sheets configuration for booking logs
    GOOGLE_SHEETS_BOOKING_ID: str | None = None
    
    # Chatwoot integration (optional)
    CHATWOOT_API_URL: str | None = None
    CHATWOOT_API_TOKEN: str | None = None
    CHATWOOT_INBOX_ID: str | None = None
    CHATWOOT_ACCOUNT_ID: int = 1

    # Saarthi website Agent API (the CRM source of truth for this branch).
    # SAARTHI_API_KEY must equal the website's AGENT_API_KEY env var.
    SAARTHI_API_URL: str = "http://localhost:3000"
    SAARTHI_API_KEY: str | None = None

    # Comma-separated phone numbers (digits only, with country code) of brokers
    # who post listings in the WhatsApp group. Messages from these numbers are
    # routed to the listing intake flow instead of the lead qualification flow.
    # Example: "919876543210,919012345678"
    BROKER_PHONE_NUMBERS: str = ""

    # WhatsApp Cloud API credentials — used by broker_intake to download media.
    WHATSAPP_ACCESS_TOKEN: str | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None

    # --- ANGC executive-assistant branch ---
    # Comma-separated WhatsApp numbers of the director (NG Sir). Only these
    # numbers can assign tasks. Example: "919876543210"
    DIRECTOR_PHONE_NUMBERS: str = ""
    # SQLite file for tasks + dashboard users (relative = under the app workdir,
    # i.e. /app/data/... in the container).
    ANGC_DB_PATH: str = "data/angc_tasks.db"
    # WhatsApp-notify the assignee when a task is created, and NG Sir when done.
    ANGC_NOTIFY_ASSIGNEES: bool = True
    # WAL journal for the tasks DB. Disable on network mounts (Azure Files/SMB
    # with nobrl) where WAL's shared-memory file is unsafe.
    ANGC_SQLITE_WAL: bool = True
    # Login email seeded for the admin (Nikhil Gupta) account.
    ANGC_ADMIN_EMAIL: str = "director@angcgroup.com"
    # First-login password for all seeded users; change via dashboard.
    ANGC_DEFAULT_PASSWORD: str = "Angc@2026"
    # Secret for signing dashboard session cookies. Set a long random string in
    # prod; if empty, a random one is generated at startup (logins reset on restart).
    ANGC_SESSION_SECRET: str = ""
    # Public URL of the dashboard, included in WhatsApp notifications (optional).
    ANGC_DASHBOARD_URL: str | None = None


settings = Settings()

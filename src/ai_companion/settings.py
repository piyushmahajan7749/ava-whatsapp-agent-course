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

    GROQ_API_KEY: str
    ELEVENLABS_API_KEY: str
    ELEVENLABS_VOICE_ID: str
    TOGETHER_API_KEY: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_API_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str
    AZURE_OPENAI_VISION_DEPLOYMENT: str
    AZURE_WHISPER_DEPLOYMENT: str = "whisper"

    QDRANT_API_KEY: str | None
    QDRANT_URL: str
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

    # Interakt integration
    INTERAKT_API_KEY: str | None = None
    INTERAKT_SEND_MESSAGE_URL: str = "https://api.interakt.ai/v1/public/message/"
    INTERAKT_WEBHOOK_SECRET: str | None = None  # Secret key for webhook signature verification

    # Staged rollout
    ALLOWLIST_NUMBERS: str | None = None  # Comma-separated E.164 (no +), e.g., "919303402193,14162780455"
    BOT_ENABLED: bool = True  # Kill switch - set to False to disable all AI responses

    # AI processing
    AI_TIMEOUT_SECONDS: int = 5
    FALLBACK_MESSAGE: str = "Thanks for reaching out. Our team will get back to you shortly."

    # Lumi onboarding
    LUMI_ENABLED: bool = True
    EXISTING_CLIENTS_DB_URL: str | None = None  # For client lookup (optional)

    # Re-engagement timing (in hours)
    NUDGE_DELAY_1_HOURS: int = 2
    NUDGE_DELAY_2_HOURS: int = 24
    ARCHIVE_DELAY_HOURS: int = 72

    # Handoff keywords (comma-separated)
    HANDOFF_KEYWORDS: str = "talk to manager,call me,human please,manager se baat,insaan se baat,refund,complaint"


settings = Settings()

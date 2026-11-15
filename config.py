"""
Configuration and settings management for the German learning bot.
"""
import os
import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
    # Load environment variables from .env file
    load_dotenv()
except ImportError:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("deutsch_bot")


@dataclass(frozen=True)
class Settings:
    # Telegram
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_allowed_chat_ids: frozenset = frozenset(
        cid.strip()
        for cid in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", os.getenv("TELEGRAM_CHAT_ID", "")).split(",")
        if cid.strip()
    )

    # Google Sheets
    spreadsheet_name: str = os.getenv("SPREADSHEET_NAME", "")
    sheet_tab_name: str = os.getenv("SHEET_TAB_NAME", "")
    cred_file: str = os.getenv("CRED_FILE", "")

    # Google GenAI
    gen_api_key: str = os.getenv("GEN_API_KEY", "")

    # Application settings
    state_file: str = "last_run.json"
    timezone: ZoneInfo = ZoneInfo("Europe/Rome")

    # Sheet Cell Coordinates
    cell_context: str = "A10"   # Vocabulary, grammar, learning summary
    cell_exercise: str = "Z10"  # Daily exercise text

    # LLM Models Fallback List
    gemini_models: tuple = (
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    )
    gemini_timeout_seconds: int = 60
    gemini_max_retries_per_model: int = 2

    # Task settings
    morning_task_max_retries: int = 5
    morning_task_retry_delay_seconds: int = 300  # 5 minutes


settings = Settings()

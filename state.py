"""
State management for tracking the last successful daily execution.
"""
import os
import json
import logging
from config import settings

logger = logging.getLogger(__name__)


def get_last_run_date(file_path: str | None = None) -> str | None:
    """Reads the last execution date (YYYY-MM-DD) from the state file."""
    target_path = file_path or settings.state_file
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("last_date")
        except Exception as e:
            logger.warning("Could not read state file %s: %s", target_path, e)
    return None


def save_last_run_date(date_str: str, file_path: str | None = None) -> None:
    """Saves the last execution date to the state file."""
    target_path = file_path or settings.state_file
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump({"last_date": date_str}, f)
        logger.info("Saved last run date: %s", date_str)
    except Exception as e:
        logger.error("Error saving state file %s: %s", target_path, e)

"""
State management for tracking the last successful daily execution and streak.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from config import settings

logger = logging.getLogger(__name__)


def _read_state(file_path: str | None = None) -> dict:
    """Reads the full state dictionary from the state file."""
    target_path = file_path or settings.state_file
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Could not read state file %s: %s", target_path, e)
    return {}


def _write_state(data: dict, file_path: str | None = None) -> None:
    """Writes the full state dictionary to the state file."""
    target_path = file_path or settings.state_file
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error("Error saving state file %s: %s", target_path, e)


def get_last_run_date(file_path: str | None = None) -> str | None:
    """Reads the last execution date (YYYY-MM-DD) from the state file."""
    return _read_state(file_path).get("last_date")


def save_last_run_date(date_str: str, file_path: str | None = None) -> None:
    """Saves the last execution date and updates the streak."""
    target_path = file_path or settings.state_file
    state = _read_state(target_path)

    old_date_str = state.get("last_date")
    old_streak = state.get("streak", 0)
    max_streak = state.get("max_streak", 0)

    # Calculate new streak
    if old_date_str:
        try:
            old_date = datetime.strptime(old_date_str, "%Y-%m-%d").date()
            new_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            diff = (new_date - old_date).days

            if diff == 1:
                # Consecutive day — extend streak
                new_streak = old_streak + 1
            elif diff == 0:
                # Same day — keep streak
                new_streak = old_streak
            else:
                # Missed one or more days — reset streak
                new_streak = 1
        except ValueError:
            new_streak = 1
    else:
        # First run ever
        new_streak = 1

    new_max = max(max_streak, new_streak)

    state["last_date"] = date_str
    state["streak"] = new_streak
    state["max_streak"] = new_max

    _write_state(state, target_path)
    logger.info("Saved state: date=%s, streak=%d, max_streak=%d", date_str, new_streak, new_max)


def get_streak(file_path: str | None = None) -> tuple[int, int]:
    """Returns (current_streak, max_streak)."""
    state = _read_state(file_path)
    return state.get("streak", 0), state.get("max_streak", 0)


def format_streak_message(streak: int, max_streak: int) -> str:
    """Formats a motivational streak message."""
    if streak == 0:
        return ""

    # Milestone messages
    if streak >= 100:
        fire = "🔥" * 5
        msg = f"\n\n{fire} STREAK: {streak} GIORNI! {fire}\nSei una leggenda! Record: {max_streak}"
    elif streak >= 30:
        msg = f"\n\n🔥🔥🔥 Streak: {streak} giorni! Incredibile! Record: {max_streak}"
    elif streak >= 7:
        msg = f"\n\n🔥🔥 Streak: {streak} giorni di fila! Record: {max_streak}"
    elif streak > 1:
        msg = f"\n\n🔥 Streak: {streak} giorni di fila!"
    else:
        msg = "\n\n💪 Primo giorno! Inizia la streak!"

    return msg

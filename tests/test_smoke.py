"""
Unit and smoke tests for the refactored bot modules.
"""
import os
import sys
import unittest
import tempfile
import py_compile
from unittest.mock import MagicMock, patch

# Provide mock stubs for external libraries if not installed in current environment
for mod in ["telebot", "telebot.types", "gspread", "google", "google.genai", "gtts", "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.background"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from prompts import Prompts
from state import get_last_run_date, save_last_run_date
from handlers.telegram import send_long_message


class TestBotModules(unittest.TestCase):
    def test_py_compile_all_files(self):
        """Verify that all python source files compile without syntax errors."""
        files = [
            "config.py",
            "state.py",
            "prompts/__init__.py",
            "prompts/templates.py",
            "services/__init__.py",
            "services/sheets.py",
            "services/gemini.py",
            "services/tts.py",
            "handlers/__init__.py",
            "handlers/telegram.py",
            "bot.py",
        ]
        for f in files:
            with self.subTest(file=f):
                py_compile.compile(f, doraise=True)

    def test_prompts_generation(self):
        """Verify prompt templates generation and marker inclusion."""
        context = "Vocabolario A2: il cane, il gatto"
        standard_prompt = Prompts.daily_exercise(context=context, is_friday=False)
        self.assertIn("This is the Exercise to do:", standard_prompt)
        self.assertNotIn(Prompts.MARKER_SUMMARY, standard_prompt)

        friday_prompt = Prompts.daily_exercise(context=context, is_friday=True)
        self.assertIn(Prompts.MARKER_SUMMARY, friday_prompt)
        self.assertIn("ALWAYS UPDATE THE PROVIDED CONTEXT!", friday_prompt)

        flashcards_prompt = Prompts.flashcards(context=context)
        self.assertIn("<tg-spoiler>", flashcards_prompt)

        audio_prompt = Prompts.audio_translation(context=context)
        self.assertIn("Translate the Italian text contained in the context above into German", audio_prompt)

        corr_prompt = Prompts.exercise_correction(exercise_context="Frase 1", student_answer="Mia risposta")
        self.assertIn("You are a teacher of German language", corr_prompt)

    def test_send_long_message_chunking(self):
        """Verify message chunking respects newline boundaries."""
        mock_bot = MagicMock()
        short_text = "Hello world"
        send_long_message(mock_bot, 12345, short_text, max_len=50)
        mock_bot.send_message.assert_called_once_with(12345, short_text)

        mock_bot.reset_mock()
        # Build 120 char text with newline in middle
        part1 = "Line one with text."
        part2 = "Line two with more text to overflow."
        long_text = f"{part1}\n{part2}"
        send_long_message(mock_bot, 12345, long_text, max_len=30)
        self.assertGreater(mock_bot.send_message.call_count, 1)

    def test_state_management(self):
        """Verify reading and saving last run date."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            save_last_run_date("2026-11-15", file_path=tmp_path)
            read_date = get_last_run_date(file_path=tmp_path)
            self.assertEqual(read_date, "2026-11-15")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()

"""
Google Sheets interaction service.
"""
import logging
import gspread
from config import settings

logger = logging.getLogger(__name__)


class SheetsService:
    def __init__(self):
        self._client = None
        self._worksheet = None

    def _get_worksheet(self):
        """Lazy-loaded worksheet connection."""
        if self._worksheet is None:
            logger.info("Initializing gspread client with credentials: %s", settings.cred_file)
            self._client = gspread.service_account(filename=settings.cred_file)
            sh = self._client.open(settings.spreadsheet_name)
            self._worksheet = sh.worksheet(settings.sheet_tab_name)
        return self._worksheet

    def get_context(self) -> str:
        """Reads learning context and vocabulary summary from cell A10."""
        ws = self._get_worksheet()
        val = ws.acell(settings.cell_context).value
        return val.strip() if val else ""

    def update_context(self, text: str) -> None:
        """Writes updated context to cell A10."""
        ws = self._get_worksheet()
        ws.update([[text]], settings.cell_context)
        logger.info("Updated cell %s with new context (length: %d)", settings.cell_context, len(text))

    def get_exercise(self) -> str:
        """Reads the current daily exercise from cell Z10."""
        ws = self._get_worksheet()
        val = ws.acell(settings.cell_exercise).value
        return val.strip() if val else ""

    def update_exercise(self, text: str) -> None:
        """Writes the exercise to cell Z10."""
        ws = self._get_worksheet()
        ws.update([[text]], settings.cell_exercise)
        logger.info("Updated cell %s with exercise (length: %d)", settings.cell_exercise, len(text))

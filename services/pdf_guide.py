import io
import logging
import re
from datetime import datetime
import weasyprint
from config import settings

logger = logging.getLogger(__name__)


def _clean_html_response(raw_html: str) -> str:
    """Strips optional ```html ... ``` fences if the model includes them."""
    cleaned = raw_html.strip()
    cleaned = re.sub(r"^```(?:html)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def html_to_pdf_buffer(html_text: str) -> io.BytesIO:
    """Renders HTML string into an in-memory PDF buffer."""
    html_clean = _clean_html_response(html_text)
    pdf_bytes = weasyprint.HTML(string=html_clean).write_pdf()
    buf = io.BytesIO(pdf_bytes)
    stamp = datetime.now(settings.timezone).strftime("%Y%m%d_%H%M")
    buf.name = f"approfondimento_tedesco_{stamp}.pdf"
    buf.seek(0)
    return buf

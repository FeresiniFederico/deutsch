"""
Text-to-speech conversion service using gTTS.
"""
import io
import logging
from gtts import gTTS

logger = logging.getLogger(__name__)


def create_audio_buffer(text: str, lang: str = "de", filename: str = "audio.mp3") -> io.BytesIO:
    """Converts text into an in-memory MP3 BytesIO buffer."""
    if not text.strip():
        raise ValueError("Cannot generate audio from empty text.")

    logger.info("Generating audio for text (length %d) with lang='%s'", len(text), lang)
    tts = gTTS(text=text, lang=lang, slow=False)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    buffer.name = filename
    return buffer

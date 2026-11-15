"""
Telegram message and command handlers.
"""
import logging
import threading
from telebot import TeleBot
from telebot.types import Message
from config import settings
from prompts.templates import Prompts
from services.sheets import SheetsService
from services.gemini import GeminiService
from services.tts import create_audio_buffer

logger = logging.getLogger(__name__)


def send_long_message(bot: TeleBot, chat_id: int | str, text: str, max_len: int = 4000) -> None:
    """Splits long text messages along newline boundaries to fit Telegram limits."""
    if not text:
        return

    while len(text) > 0:
        if len(text) <= max_len:
            bot.send_message(chat_id, text)
            break

        chunk = text[:max_len]
        last_newline = chunk.rfind("\n")
        split_index = last_newline + 1 if last_newline > max_len // 2 else max_len

        bot.send_message(chat_id, text[:split_index])
        text = text[split_index:]


def send_audio_message(
    bot: TeleBot,
    chat_id: int | str,
    text: str,
    lang: str = "de",
    caption: str = "🎧 Ecco l'audio dell'esercizio!",
    filename: str = "esercizio.mp3",
) -> None:
    """Converts text to MP3 audio and sends it to the specified chat."""
    if not text.strip():
        bot.send_message(chat_id, "⚠️ Non c'è nessun testo da convertire in audio.")
        return

    try:
        audio_buf = create_audio_buffer(text, lang=lang, filename=filename)
        # Telegram captions are capped at 1024 characters
        if len(caption) > 1024:
            caption = caption[:1020] + "..."
        bot.send_audio(chat_id, audio_buf, caption=caption)
    except Exception as e:
        logger.error("Failed to generate or send audio: %s", e)
        bot.send_message(chat_id, f"⚠️ Errore durante la creazione dell'audio: {e}")


def handle_audio_command(bot: TeleBot, chat_id: int | str, sheets: SheetsService, gemini: GeminiService) -> None:
    """Handles 'audio' request: translates Z10 context to German via Gemini, then generates TTS."""
    try:
        bot.send_message(chat_id, "🎙️ Elaborazione del testo con Gemini in corso...")
        exercise_text = sheets.get_exercise()

        if not exercise_text:
            bot.send_message(chat_id, f"⚠️ La cella {settings.cell_exercise} è vuota, nessun testo da elaborare.")
            return

        prompt = Prompts.audio_translation(exercise_text)
        translated_text = gemini.generate_content(prompt)

        if not translated_text:
            bot.send_message(chat_id, "⚠️ Gemini non ha restituito alcuna risposta.")
            return

        bot.send_message(chat_id, "🔊 Conversione della risposta in audio in corso...")
        caption = f"🎧 **Ripasso audio da Gemini:**\n\n{translated_text}"
        send_audio_message(
            bot=bot,
            chat_id=chat_id,
            text=translated_text,
            lang="de",
            caption=caption,
            filename="ripasso_gemini.mp3",
        )
    except Exception as e:
        logger.error("Error in audio command: %s", e)
        bot.send_message(chat_id, f"⚠️ Errore durante la creazione dell'audio: {e}")


def handle_flashcards_command(bot: TeleBot, chat_id: int | str, sheets: SheetsService, gemini: GeminiService) -> None:
    """Handles 'flashcards' request: generates HTML spoiler flashcards from cell A10."""
    try:
        bot.send_message(chat_id, "🃏 Generazione delle Flashcards interattive in corso...")
        context_text = sheets.get_context()

        if not context_text:
            bot.send_message(chat_id, f"⚠️ La cella {settings.cell_context} è vuota, impossibile generare le flashcards.")
            return

        prompt = Prompts.flashcards(context_text)
        flashcards_reply = gemini.generate_content(prompt)

        if not flashcards_reply:
            bot.send_message(chat_id, "⚠️ Gemini non ha restituito alcuna risposta per le flashcards.")
            return

        final_msg = (
            f"🃏 <b>Le tue Flashcards Interattive:</b>\n"
            f"<i>(Clicca sui testi nascosti per svelare la traduzione)</i>\n\n"
            f"{flashcards_reply}"
        )
        bot.send_message(chat_id, final_msg, parse_mode="HTML")
    except Exception as e:
        logger.error("Error generating flashcards: %s", e)
        bot.send_message(chat_id, f"⚠️ Errore durante la creazione delle flashcards: {e}")


def handle_context_command(bot: TeleBot, chat_id: int | str, sheets: SheetsService) -> None:
    """Handles 'context' request: retrieves current learning summary from cell A10."""
    try:
        context_text = sheets.get_context()
        if not context_text:
            bot.send_message(chat_id, f"⚠️ La cella {settings.cell_context} è attualmente vuota.")
        else:
            send_long_message(chat_id=chat_id, bot=bot, text=f"📚 **Contesto attuale (Cella {settings.cell_context}):**\n\n{context_text}")
    except Exception as e:
        logger.error("Error fetching context: %s", e)
        bot.send_message(chat_id, f"⚠️ Errore nel recupero del contesto: {e}")


def handle_student_solution(
    bot: TeleBot,
    chat_id: int | str,
    solution_text: str,
    sheets: SheetsService,
    gemini: GeminiService,
    reply_to_message_id: int | None = None,
) -> None:
    """Handles student exercise submissions: compares against cell Z10 and returns teacher feedback."""
    try:
        exercise_context = sheets.get_exercise()
        logger.info("Correction request received from chat %s. Exercise length: %d", chat_id, len(exercise_context))

        prompt = Prompts.exercise_correction(
            exercise_context=exercise_context,
            student_answer=solution_text,
        )
        correction_reply = gemini.generate_content(prompt)
        send_long_message(bot=bot, chat_id=chat_id, text=correction_reply)
    except Exception as e:
        logger.error("Error correcting student solution: %s", e)
        err_msg = f"⚠️ Errore nell'elaborazione della richiesta: {e}"
        if reply_to_message_id:
            bot.send_message(chat_id, err_msg, reply_to_message_id=reply_to_message_id)
        else:
            bot.send_message(chat_id, err_msg)


def register_handlers(bot: TeleBot, sheets: SheetsService, gemini: GeminiService, trigger_morning_task_fn) -> None:
    """Registers message and command routes on the TeleBot instance."""

    @bot.message_handler(func=lambda msg: bool(msg.text and msg.text.strip()))
    def on_text_message(message: Message):
        text = message.text.strip()
        command = text.lower()
        chat_id = message.chat.id
        logger.info("Message received from %s: '%s'", chat_id, text)

        # Auth guard: ignore messages from unauthorized chats
        if str(chat_id) not in settings.telegram_allowed_chat_ids:
            logger.warning("Unauthorized message from chat_id %s. Ignoring.", chat_id)
            bot.reply_to(message, "⛔ Non sei autorizzato ad usare questo bot.")
            return

        if command in ("ancora", "/ancora"):
            bot.reply_to(message, "🔄 Comando 'ancora' ricevuto. Avvio manuale del task mattutino...")
            threading.Thread(target=trigger_morning_task_fn, daemon=True).start()
            return

        if command in ("audio", "/audio"):
            bot.reply_to(message, "🎙️ Richiesta audio ricevuta. Elaborazione in corso...")
            threading.Thread(
                target=handle_audio_command,
                args=(bot, chat_id, sheets, gemini),
                daemon=True,
            ).start()
            return

        if command in ("context", "/context"):
            handle_context_command(bot, chat_id, sheets)
            return

        if command in ("flashcards", "flashcard", "/flashcards", "/flashcard"):
            bot.reply_to(message, "🃏 Preparazione delle flashcards dal contesto...")
            threading.Thread(
                target=handle_flashcards_command,
                args=(bot, chat_id, sheets, gemini),
                daemon=True,
            ).start()
            return

        # Default fallback: Treat as a student exercise submission
        threading.Thread(
            target=handle_student_solution,
            args=(bot, chat_id, text, sheets, gemini, message.message_id),
            daemon=True,
        ).start()

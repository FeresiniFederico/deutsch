"""
Main entry point for the German Learning Telegram Bot.
"""
import time
import threading
import logging
from datetime import datetime
from telebot import TeleBot
from apscheduler.schedulers.background import BackgroundScheduler

from config import settings, logger
from state import get_last_run_date, save_last_run_date
from prompts import Prompts
from services import SheetsService, GeminiService
from handlers import register_handlers, send_long_message

# Service instances
sheets_service = SheetsService()
gemini_service = GeminiService()
bot = TeleBot(settings.telegram_token)


def run_morning_task() -> None:
    """Executes the daily morning exercise generator with retry logic."""
    max_retries = settings.morning_task_max_retries
    retry_delay = settings.morning_task_retry_delay_seconds

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Starting morning task (Attempt %d/%d)...", attempt, max_retries)

            # 1. Fetch learning context from cell A10
            context_text = sheets_service.get_context()
            today_str = datetime.now(settings.timezone).strftime("%Y-%m-%d")

            if not context_text:
                logger.info("Context cell %s is empty. Task completed without sending.", settings.cell_context)
                save_last_run_date(today_str)
                return

            # 2. Build dynamic prompt (Friday includes summary update instructions)
            now = datetime.now(settings.timezone)
            is_friday = (now.weekday() == 4)
            prompt = Prompts.daily_exercise(context=context_text, is_friday=is_friday)

            # 3. Call Gemini
            gemini_reply = gemini_service.generate_content(prompt)

            # 4. Handle summary marker
            if Prompts.MARKER_SUMMARY in gemini_reply:
                parts = gemini_reply.split(Prompts.MARKER_SUMMARY, 1)
                telegram_exercise = parts[0].strip()
                new_context = parts[1].strip()

                # Update context in cell A10
                sheets_service.update_context(new_context)
                logger.info("New learning context successfully saved to %s.", settings.cell_context)

                # Send exercise to Telegram and save to cell Z10
                if telegram_exercise:
                    msg = f"🌅{telegram_exercise}"
                    send_long_message(bot=bot, chat_id=settings.telegram_chat_id, text=msg)
                    sheets_service.update_exercise(telegram_exercise)
            else:
                # Normal exercise flow
                msg = f"🌅 {gemini_reply}"
                send_long_message(bot=bot, chat_id=settings.telegram_chat_id, text=msg)
                sheets_service.update_exercise(gemini_reply)

            # Mark today as completed
            save_last_run_date(today_str)
            logger.info("Morning task completed successfully.")
            return

        except Exception as e:
            err_msg = str(e)
            logger.error("Morning task attempt %d failed: %s", attempt, err_msg)

            if attempt < max_retries:
                logger.info("Retrying in %d seconds...", retry_delay)
                time.sleep(retry_delay)
            else:
                logger.critical("All %d morning task attempts failed. Sending alert to Telegram.", max_retries)
                try:
                    alert_msg = (
                        f"❌ **ERRORE CRITICO Task Mattutino**\n\n"
                        f"Il task delle 8:00 è fallito dopo {max_retries} tentativi consecutivi.\n\n"
                        f"**Errore:**\n`{err_msg}`"
                    )
                    bot.send_message(settings.telegram_chat_id, alert_msg)
                except Exception as tg_err:
                    logger.error("Failed to send error notification on Telegram: %s", tg_err)


def main() -> None:
    """Bootstraps services, registers handlers, and starts scheduler and polling."""
    logger.info("Starting German Learning Bot...")

    # Register message routes
    register_handlers(
        bot=bot,
        sheets=sheets_service,
        gemini=gemini_service,
        trigger_morning_task_fn=run_morning_task,
    )

    now = datetime.now(settings.timezone)
    today = now.strftime("%Y-%m-%d")
    last_run = get_last_run_date()

    logger.info("Last recorded run: %s (Today: %s)", last_run, today)

    # Catch-up check: If today's run was missed and it is already 8:00 or later
    if last_run != today:
        if now.hour >= 8:
            logger.info("8:00 AM has already passed today and task was not executed. Triggering immediate run...")
            threading.Thread(target=run_morning_task, daemon=True).start()
        else:
            logger.info("Task not yet executed today, but current time is before 8:00 AM. Scheduler will trigger.")

    # Schedule daily morning task at 07:00 (Europe/Rome timezone)
    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(run_morning_task, "cron", hour=7, minute=0)
    scheduler.start()
    logger.info("Scheduler started. Daily task set for 07:00 Europe/Rome.")

    logger.info("Bot listening for Telegram messages (Long Polling)...")
    try:
        bot.infinity_polling()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down bot...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()

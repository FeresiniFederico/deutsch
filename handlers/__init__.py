"""Handlers package for Telegram messages and commands."""
from handlers.telegram import register_handlers, send_long_message

__all__ = ["register_handlers", "send_long_message"]

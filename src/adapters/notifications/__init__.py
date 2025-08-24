"""
Notification adapter implementations.

This module contains adapters for various notification channels.
"""

from .telegram import TelegramAdapter

__all__ = ['TelegramAdapter']
"""
Storage adapter implementations.

This module contains adapters for various data storage backends.
"""

from .sqlite import SQLiteAdapter

__all__ = ['SQLiteAdapter']
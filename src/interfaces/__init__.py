"""
Abstract interfaces (ports) for the CV Review System.

This module defines the abstract interfaces that adapters must implement,
following the Ports and Adapters (Hexagonal) architecture pattern.
"""

from .repository import RepositoryAdapter
from .analyzer import AnalyzerAdapter
from .storage import StorageAdapter
from .notification import NotificationAdapter

__all__ = [
    'RepositoryAdapter',
    'AnalyzerAdapter',
    'StorageAdapter',
    'NotificationAdapter'
]
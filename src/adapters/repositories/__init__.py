"""
Repository adapter implementations.

This module contains adapters for various repository hosting services.
"""

from .github import GitHubAdapter

__all__ = ['GitHubAdapter']
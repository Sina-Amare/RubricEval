"""
Adapter implementations for external services.

This module contains concrete implementations of the interfaces
defined in the interfaces module.

Available adapters:
- analyzers.openrouter: OpenRouter LLM analyzer adapter
"""

# Import main adapters for easy access
from .analyzers import OpenRouterAdapter

__all__ = ['OpenRouterAdapter']
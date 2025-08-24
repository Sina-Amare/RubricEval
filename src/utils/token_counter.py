"""
Token counting utilities for LLM analysis.

This module provides token estimation for different LLM providers
to help manage context windows and API costs.
"""

import re
from typing import Dict, Optional
from utils.logger import setup_logger

# Initialize logger for this module
logger = setup_logger(__name__)


class TokenCounter:
    """
    Token counting utility for various LLM models.
    
    Provides estimation methods for different tokenization approaches
    used by various LLM providers.
    """
    
    # Average characters per token for different model families
    MODEL_CHAR_PER_TOKEN = {
        'gpt': 4,      # OpenAI models
        'claude': 3.8,  # Anthropic models
        'gemini': 4.2,  # Google models
        'default': 4    # Conservative default
    }
    
    @classmethod
    def estimate_tokens(cls, text: str, model_family: str = 'default') -> int:
        """
        Estimate token count for given text.
        
        Uses a simple character-based estimation approach that works
        reasonably well across different tokenization schemes.
        
        Args:
            text: Text to estimate tokens for
            model_family: Model family ('gpt', 'claude', 'gemini', 'default')
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
            
        # Get character-per-token ratio for model family
        chars_per_token = cls.MODEL_CHAR_PER_TOKEN.get(model_family, cls.MODEL_CHAR_PER_TOKEN['default'])
        
        # Simple character-based estimation
        char_count = len(text)
        estimated_tokens = int(char_count / chars_per_token)
        
        logger.debug(f"Estimated {estimated_tokens} tokens for {char_count} characters")
        return estimated_tokens
    
    @classmethod
    def estimate_prompt_tokens(cls, system_prompt: str, user_prompt: str, 
                              model_family: str = 'default') -> Dict[str, int]:
        """
        Estimate tokens for a complete prompt with system and user messages.
        
        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            model_family: Model family identifier
            
        Returns:
            Dictionary with token counts for system, user, and total
        """
        system_tokens = cls.estimate_tokens(system_prompt, model_family)
        user_tokens = cls.estimate_tokens(user_prompt, model_family)
        
        # Add small overhead for message formatting
        formatting_overhead = 10
        total_tokens = system_tokens + user_tokens + formatting_overhead
        
        return {
            'system_tokens': system_tokens,
            'user_tokens': user_tokens,
            'formatting_overhead': formatting_overhead,
            'total_tokens': total_tokens
        }
    
    @classmethod
    def can_fit_context(cls, text: str, max_tokens: int, 
                       model_family: str = 'default') -> bool:
        """
        Check if text fits within model's context window.
        
        Args:
            text: Text to check
            max_tokens: Maximum context window size
            model_family: Model family identifier
            
        Returns:
            True if text fits within context, False otherwise
        """
        estimated = cls.estimate_tokens(text, model_family)
        return estimated <= max_tokens
    
    @classmethod
    def get_model_family(cls, model_name: str) -> str:
        """
        Determine model family from model name.
        
        Args:
            model_name: Full model name/identifier
            
        Returns:
            Model family identifier
        """
        model_lower = model_name.lower()
        
        if 'gpt' in model_lower or 'openai' in model_lower:
            return 'gpt'
        elif 'claude' in model_lower or 'anthropic' in model_lower:
            return 'claude'
        elif 'gemini' in model_lower or 'google' in model_lower:
            return 'gemini'
        else:
            return 'default'
    
    @classmethod
    def truncate_to_fit(cls, text: str, max_tokens: int, 
                       model_family: str = 'default') -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum token limit
            model_family: Model family identifier
            
        Returns:
            Truncated text that fits within token limit
        """
        if cls.can_fit_context(text, max_tokens, model_family):
            return text
        
        chars_per_token = cls.MODEL_CHAR_PER_TOKEN.get(model_family, cls.MODEL_CHAR_PER_TOKEN['default'])
        max_chars = int(max_tokens * chars_per_token * 0.95)  # 95% safety margin
        
        if len(text) <= max_chars:
            return text
        
        logger.warning(f"Truncating text from {len(text)} to {max_chars} characters")
        
        # Try to truncate at a reasonable boundary
        truncated = text[:max_chars]
        
        # Find last complete line or code block
        last_newline = truncated.rfind('\n')
        if last_newline > max_chars * 0.9:  # If we're not losing too much
            truncated = truncated[:last_newline]
        
        return truncated + "\n\n[Content truncated due to token limits]"


def estimate_tokens(text: str, model_name: str = None) -> int:
    """
    Convenience function for token estimation.
    
    Args:
        text: Text to estimate tokens for
        model_name: Optional model name to determine family
        
    Returns:
        Estimated token count
    """
    if model_name:
        model_family = TokenCounter.get_model_family(model_name)
    else:
        model_family = 'default'
    
    return TokenCounter.estimate_tokens(text, model_family)


def can_fit_model_context(text: str, model_name: str, max_context: int) -> bool:
    """
    Check if text fits within model's context window.
    
    Args:
        text: Text to check
        model_name: Model name to determine tokenization approach
        max_context: Maximum context window size
        
    Returns:
        True if text fits, False otherwise
    """
    model_family = TokenCounter.get_model_family(model_name)
    return TokenCounter.can_fit_context(text, max_context, model_family)

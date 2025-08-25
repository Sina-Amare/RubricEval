"""
Prompt management utility for loading and formatting prompts.

This module provides utilities to load prompt templates from files
and format them with dynamic values.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Base path for prompts
PROMPTS_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "data" / "prompts"


class PromptLoader:
    """
    Loads and manages prompt templates from files.
    
    This class provides methods to load prompts from markdown files
    and format them with provided parameters.
    """
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize the prompt loader.
        
        Args:
            prompts_dir: Optional custom prompts directory path
        """
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._cache: Dict[str, str] = {}
        logger.info(f"PromptLoader initialized with directory: {self.prompts_dir}")
    
    def load_prompt(self, prompt_path: str, use_cache: bool = True) -> str:
        """
        Load a prompt template from file.
        
        Args:
            prompt_path: Relative path to prompt file (e.g., "analysis/code_review.md")
            use_cache: Whether to use cached version if available
            
        Returns:
            Prompt template content
            
        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        if use_cache and prompt_path in self._cache:
            logger.debug(f"Using cached prompt: {prompt_path}")
            return self._cache[prompt_path]
        
        full_path = self.prompts_dir / prompt_path
        
        if not full_path.exists():
            error_msg = f"Prompt file not found: {full_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self._cache[prompt_path] = content
            logger.debug(f"Loaded prompt from: {full_path}")
            return content
            
        except Exception as e:
            error_msg = f"Failed to load prompt from {full_path}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def format_prompt(self, prompt_path: str, **kwargs) -> str:
        """
        Load and format a prompt template with provided values.
        
        Args:
            prompt_path: Relative path to prompt file
            **kwargs: Values to format into the prompt template
            
        Returns:
            Formatted prompt ready for use
            
        Example:
            >>> loader = PromptLoader()
            >>> prompt = loader.format_prompt(
            ...     "analysis/code_review.md",
            ...     role="backend",
            ...     github_url="https://github.com/user/repo",
            ...     file_count=10
            ... )
        """
        template = self.load_prompt(prompt_path)
        
        try:
            formatted = template.format(**kwargs)
            logger.debug(f"Formatted prompt {prompt_path} with {len(kwargs)} parameters")
            return formatted
            
        except KeyError as e:
            # Don't fail entirely - just return template with unfilled variables
            logger.warning(f"Some template variables not provided for {prompt_path}: {e}")
            # Return the template as-is, the LLM will figure it out
            return template
        except Exception as e:
            error_msg = f"Failed to format prompt {prompt_path}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def clear_cache(self):
        """Clear the prompt cache."""
        self._cache.clear()
        logger.debug("Prompt cache cleared")


# Singleton instance for convenience
_default_loader = None


def get_prompt_loader() -> PromptLoader:
    """
    Get the default prompt loader instance.
    
    Returns:
        Singleton PromptLoader instance
    """
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


def load_prompt(prompt_path: str, **kwargs) -> str:
    """
    Convenience function to load and format a prompt.
    
    Args:
        prompt_path: Relative path to prompt file
        **kwargs: Values to format into the prompt
        
    Returns:
        Formatted prompt string
        
    Example:
        >>> prompt = load_prompt(
        ...     "analysis/code_review.md",
        ...     role="frontend",
        ...     github_url="https://github.com/user/repo"
        ... )
    """
    loader = get_prompt_loader()
    if kwargs:
        return loader.format_prompt(prompt_path, **kwargs)
    return loader.load_prompt(prompt_path)


def escape_markdown(text: str) -> str:
    """
    Escape special markdown characters for Telegram.
    
    Args:
        text: Text to escape
        
    Returns:
        Text with escaped markdown characters
    """
    if not text:
        return text
    
    # Characters that need escaping in Telegram MarkdownV2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text
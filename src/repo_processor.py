"""
Repository processing module for CV Review Bot.

This module provides backward compatibility and facade pattern
for the new adapter-based repository processing system.

Legacy Interface - redirects to GitHubAdapter for actual processing.
"""

import asyncio
from typing import Dict, Optional

from adapters.repositories.github import GitHubAdapter
from core.models import Role, RepositoryContent
from core.exceptions import RepositoryError, ValidationError
from config import MAX_TOKENS
from utils.logger import setup_logger, log_performance

# Initialize logger for this module
logger = setup_logger(__name__)


class RepositoryProcessor:
    """
    Legacy repository processor - provides backward compatibility.
    
    This class acts as a facade for the new GitHubAdapter, maintaining
    the existing interface while delegating to the new modular system.
    
    Deprecated: Use GitHubAdapter directly for new code.
    """
    
    def __init__(self, role: str, max_tokens: int = MAX_TOKENS):
        """
        Initialize the repository processor.
        
        Args:
            role: The role type ('backend' or 'frontend')
            max_tokens: Maximum token limit for LLM context
        """
        # Convert string role to enum
        try:
            if role.lower() == 'backend':
                self.role = Role.BACKEND
            elif role.lower() == 'frontend':
                self.role = Role.FRONTEND
            else:
                raise ValueError(f"Invalid role: {role}. Must be 'backend' or 'frontend'")
        except Exception as e:
            logger.error(f"Failed to initialize role: {e}")
            raise
        
        self.max_tokens = max_tokens
        
        # Initialize the GitHub adapter
        self.github_adapter = GitHubAdapter(max_tokens=max_tokens)
        
        logger.info(f"RepositoryProcessor initialized for role: {self.role.value} (using GitHubAdapter)")
        logger.warning("RepositoryProcessor is deprecated. Use GitHubAdapter directly for new code.")
    
    @log_performance("repository_processing")
    async def process_repository(self, github_url: str) -> Dict:
        """
        Main method to process a GitHub repository.
        
        Legacy interface - delegates to GitHubAdapter for actual processing.
        
        Args:
            github_url: The GitHub repository URL to process
            
        Returns:
            Dict containing:
            - success: Boolean indicating success
            - content: Optimized repository content (as formatted string)
            - file_count: Number of files processed
            - total_tokens: Total token count
            - error: Error message if failed
        """
        try:
            logger.info(f"Processing repository (legacy interface): {github_url}")
            
            # Use the new adapter for processing
            repo_content = await self.github_adapter.fetch_repository(github_url, self.role)
            
            # Convert to optimized content string format (legacy format)
            optimized_content = self._convert_to_legacy_format(repo_content)
            
            logger.info(f"Successfully processed repository: {len(repo_content.files)} files, {repo_content.total_tokens} tokens")
            
            return {
                'success': True,
                'content': optimized_content,
                'file_count': len(repo_content.files),
                'total_tokens': repo_content.total_tokens
            }
            
        except (ValidationError, RepositoryError) as e:
            error_msg = f"Repository processing failed: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Unexpected error during repository processing: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
        finally:
            # Ensure cleanup
            await self.github_adapter.cleanup()
    
    def _convert_to_legacy_format(self, repo_content: RepositoryContent) -> str:
        """
        Convert new RepositoryContent format to legacy string format.
        
        This method maintains backward compatibility by converting the new
        structured RepositoryContent to the old optimized string format.
        
        Args:
            repo_content: New format repository content
            
        Returns:
            Legacy formatted content string
        """
        optimized_content = []
        
        # Add repository structure (from new format)
        optimized_content.append(f"# Repository Structure\n{repo_content.structure}\n")
        
        # Add files in legacy format
        for file_info in repo_content.files:
            # Handle truncated files (indicated by path ending with [TRUNCATED])
            if file_info.path.endswith("[TRUNCATED]"):
                clean_path = file_info.path.replace(" [TRUNCATED]", "")
                optimized_content.append(
                    f"\n## File: {clean_path} (Priority: {file_info.priority}, TRUNCATED)\n"
                    f"```\n{file_info.content}\n```\n"
                )
            else:
                optimized_content.append(
                    f"\n## File: {file_info.path} (Priority: {file_info.priority})\n"
                    f"```\n{file_info.content}\n```\n"
                )
        
        result = ''.join(optimized_content)
        logger.debug(f"Converted new format to legacy format: {len(result)} characters")
        
        return result
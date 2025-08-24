"""
Repository adapter interface.

This module defines the abstract interface for repository sources
(GitHub, GitLab, Bitbucket, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from core.models import RepositoryContent, FileInfo, Role


class RepositoryAdapter(ABC):
    """
    Abstract interface for repository source adapters.
    
    Implementations of this interface handle fetching and processing
    code from various repository hosting services.
    """
    
    @abstractmethod
    async def validate_url(self, url: str) -> bool:
        """
        Validate if the URL is a valid repository URL for this adapter.
        
        Args:
            url: Repository URL to validate
            
        Returns:
            True if URL is valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def fetch_repository(self, url: str, role: Role) -> RepositoryContent:
        """
        Fetch and process repository content.
        
        This method should:
        1. Clone or fetch the repository
        2. Extract relevant files based on role
        3. Calculate token counts
        4. Generate repository structure
        
        Args:
            url: Repository URL
            role: Role to optimize file selection for
            
        Returns:
            Processed repository content
            
        Raises:
            RepositoryError: If fetching or processing fails
            TokenLimitError: If repository exceeds token limits
        """
        pass
    
    @abstractmethod
    async def get_repository_info(self, url: str) -> Dict[str, Any]:
        """
        Get repository metadata without fetching content.
        
        This method should return basic information like:
        - Repository name
        - Owner
        - Description
        - Primary language
        - Size
        - Last updated
        
        Args:
            url: Repository URL
            
        Returns:
            Dictionary containing repository metadata
            
        Raises:
            RepositoryError: If metadata fetching fails
        """
        pass
    
    @abstractmethod
    def extract_repo_id(self, url: str) -> str:
        """
        Extract repository identifier from URL.
        
        Args:
            url: Repository URL
            
        Returns:
            Repository identifier (e.g., "owner/repo")
            
        Raises:
            ValidationError: If URL format is invalid
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Clean up any temporary resources.
        
        This method should remove temporary files, close connections, etc.
        """
        pass
    
    # Optional methods with default implementations
    
    def get_supported_platforms(self) -> List[str]:
        """
        Get list of supported repository platforms.
        
        Returns:
            List of platform names (e.g., ["github.com", "gitlab.com"])
        """
        return []
    
    def get_file_patterns(self, role: Role) -> Dict[str, List[str]]:
        """
        Get file patterns to prioritize for a given role.
        
        Args:
            role: Role to get patterns for
            
        Returns:
            Dictionary with priority levels and file patterns
        """
        return {
            "critical": [],
            "important": [],
            "useful": []
        }
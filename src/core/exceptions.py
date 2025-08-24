"""
Custom exceptions for the CV Review System.

This module defines custom exception classes used throughout
the application for better error handling and debugging.
"""


class CVReviewException(Exception):
    """Base exception for all CV Review System exceptions."""
    
    def __init__(self, message: str, details: dict = None):
        """
        Initialize exception with message and optional details.
        
        Args:
            message: Error message
            details: Additional error details as dictionary
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(CVReviewException):
    """
    Raised when input validation fails.
    
    Used for invalid URLs, roles, or other user inputs.
    """
    pass


class RepositoryError(CVReviewException):
    """
    Raised when repository operations fail.
    
    This includes cloning failures, access issues, or invalid repositories.
    """
    pass


class AnalysisError(CVReviewException):
    """
    Raised when code analysis fails.
    
    This includes LLM API failures, parsing errors, or analysis timeouts.
    """
    pass


class StorageError(CVReviewException):
    """
    Raised when database operations fail.
    
    This includes connection issues, query failures, or data integrity errors.
    """
    pass


class ConfigurationError(CVReviewException):
    """
    Raised when configuration is invalid or missing.
    
    This includes missing environment variables or invalid configuration values.
    """
    pass


class RateLimitError(CVReviewException):
    """
    Raised when rate limits are exceeded.
    
    This includes API rate limits or system throttling.
    """
    
    def __init__(self, message: str, retry_after: int = None, details: dict = None):
        """
        Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retry
            details: Additional error details
        """
        super().__init__(message, details)
        self.retry_after = retry_after


class TokenLimitError(AnalysisError):
    """
    Raised when repository exceeds token limits.
    
    This indicates the repository is too large for analysis.
    """
    
    def __init__(self, message: str, token_count: int, limit: int, details: dict = None):
        """
        Initialize token limit error.
        
        Args:
            message: Error message
            token_count: Actual token count
            limit: Token limit exceeded
            details: Additional error details
        """
        super().__init__(message, details)
        self.token_count = token_count
        self.limit = limit


class NotificationError(CVReviewException):
    """
    Raised when notification delivery fails.
    
    This includes Telegram API failures or message formatting issues.
    """
    pass
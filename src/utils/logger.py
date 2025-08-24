"""
Robust logging system for CV Review Bot.

This module provides a comprehensive logging configuration with:
- Different log levels for different components
- Log rotation to prevent disk overflow
- Sensitive data masking
- Structured logging format
- Performance metrics tracking
"""

import logging
import logging.handlers
import os
import sys
import re
from datetime import datetime
from typing import Optional, Any, Dict
from functools import wraps
import time

# Create logs directory if it doesn't exist
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Log file paths
APP_LOG_FILE = os.path.join(LOG_DIR, 'app.log')
ERROR_LOG_FILE = os.path.join(LOG_DIR, 'error.log')
AUDIT_LOG_FILE = os.path.join(LOG_DIR, 'audit.log')
PERFORMANCE_LOG_FILE = os.path.join(LOG_DIR, 'performance.log')

# Sensitive patterns to mask in logs
SENSITIVE_PATTERNS = [
    (r'(bot_token["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', r'\1***MASKED***'),
    (r'(openrouter_key["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', r'\1***MASKED***'),
    (r'(api_key["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', r'\1***MASKED***'),
    (r'(password["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', r'\1***MASKED***'),
    (r'(token["\']?\s*[:=]\s*["\']?)([^"\',\s]+)', r'\1***MASKED***'),
    (r'(\d{6,})', r'***ID_MASKED***'),  # Mask long numbers (potential user IDs)
]


class SensitiveDataFilter(logging.Filter):
    """
    Filter to mask sensitive data in log messages.
    
    This filter applies regex patterns to mask sensitive information
    like API keys, tokens, and user IDs before they are logged.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Apply sensitive data masking to log record.
        
        Args:
            record: The log record to filter
            
        Returns:
            bool: Always True (we don't block, just mask)
        """
        if hasattr(record, 'msg'):
            message = str(record.msg)
            for pattern, replacement in SENSITIVE_PATTERNS:
                message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
            record.msg = message
            
        # Also mask arguments
        if hasattr(record, 'args') and record.args:
            masked_args = []
            for arg in record.args:
                arg_str = str(arg)
                for pattern, replacement in SENSITIVE_PATTERNS:
                    arg_str = re.sub(pattern, replacement, arg_str, flags=re.IGNORECASE)
                masked_args.append(arg_str)
            record.args = tuple(masked_args)
            
        return True


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured logging.
    
    Provides consistent, parseable log format with additional context.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with structured data.
        
        Args:
            record: The log record to format
            
        Returns:
            str: Formatted log message
        """
        # Add custom fields if available
        extra_fields = []
        if hasattr(record, 'user_id'):
            extra_fields.append(f"user_id={record.user_id}")
        if hasattr(record, 'submission_id'):
            extra_fields.append(f"submission_id={record.submission_id}")
        if hasattr(record, 'duration'):
            extra_fields.append(f"duration={record.duration:.3f}s")
            
        # Build the structured message
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        level = record.levelname
        module = record.module
        func = record.funcName
        line = record.lineno
        message = super().format(record)
        
        structured_msg = f"[{timestamp}] [{level}] [{module}:{func}:{line}]"
        if extra_fields:
            structured_msg += f" [{' | '.join(extra_fields)}]"
        structured_msg += f" - {message}"
        
        return structured_msg


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with comprehensive configuration.
    
    Creates a logger with:
    - Console output for INFO and above
    - File output with rotation
    - Error-specific file for ERROR and above
    - Sensitive data filtering
    
    Args:
        name: Name of the logger (usually __name__)
        level: Logging level (default: INFO)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
        
    logger.setLevel(level)
    
    # Create formatters
    detailed_formatter = StructuredFormatter(
        '%(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler - INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    console_handler.addFilter(SensitiveDataFilter())
    
    # Main log file handler with rotation - DEBUG and above
    file_handler = logging.handlers.RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    file_handler.addFilter(SensitiveDataFilter())
    
    # Error log file handler - ERROR and above
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    error_handler.addFilter(SensitiveDataFilter())
    
    # Add all handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    
    return logger


def get_audit_logger() -> logging.Logger:
    """
    Get a specialized audit logger for tracking important events.
    
    Used for logging:
    - User submissions
    - Analysis results
    - Manager actions
    - System state changes
    
    Returns:
        logging.Logger: Configured audit logger
    """
    audit_logger = logging.getLogger('audit')
    
    if audit_logger.handlers:
        return audit_logger
        
    audit_logger.setLevel(logging.INFO)
    
    # Audit file handler with daily rotation
    audit_handler = logging.handlers.TimedRotatingFileHandler(
        AUDIT_LOG_FILE,
        when='midnight',
        interval=1,
        backupCount=30,  # Keep 30 days of audit logs
        encoding='utf-8'
    )
    
    audit_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    audit_handler.setFormatter(audit_formatter)
    audit_handler.addFilter(SensitiveDataFilter())
    audit_logger.addHandler(audit_handler)
    
    return audit_logger


def get_performance_logger() -> logging.Logger:
    """
    Get a specialized performance logger for tracking metrics.
    
    Used for logging:
    - API response times
    - Database query durations
    - Analysis processing times
    - Memory usage
    
    Returns:
        logging.Logger: Configured performance logger
    """
    perf_logger = logging.getLogger('performance')
    
    if perf_logger.handlers:
        return perf_logger
        
    perf_logger.setLevel(logging.INFO)
    
    # Performance file handler
    perf_handler = logging.handlers.RotatingFileHandler(
        PERFORMANCE_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    
    perf_formatter = logging.Formatter(
        '%(asctime)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S.%f'
    )
    
    perf_handler.setFormatter(perf_formatter)
    perf_logger.addHandler(perf_handler)
    
    return perf_logger


def log_performance(operation: str):
    """
    Decorator to log performance metrics for functions.
    
    Tracks execution time and logs it to the performance logger.
    
    Args:
        operation: Name of the operation being tracked
        
    Example:
        @log_performance("database_query")
        def get_user(user_id: int):
            # ... database operation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            perf_logger = get_performance_logger()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                perf_logger.info(
                    f"OPERATION: {operation} | "
                    f"FUNCTION: {func.__name__} | "
                    f"DURATION: {duration:.3f}s | "
                    f"STATUS: SUCCESS"
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                perf_logger.error(
                    f"OPERATION: {operation} | "
                    f"FUNCTION: {func.__name__} | "
                    f"DURATION: {duration:.3f}s | "
                    f"STATUS: FAILED | "
                    f"ERROR: {str(e)}"
                )
                
                raise
                
        return wrapper
    return decorator


def log_user_action(logger: logging.Logger, action: str, 
                    user_id: Optional[str] = None, 
                    details: Optional[Dict[str, Any]] = None):
    """
    Log a user action with context.
    
    Args:
        logger: Logger instance to use
        action: Description of the action
        user_id: Telegram user ID (optional)
        details: Additional details as dictionary (optional)
    """
    message = f"ACTION: {action}"
    
    if user_id:
        message += f" | USER_ID: {user_id}"
        
    if details:
        details_str = " | ".join([f"{k}={v}" for k, v in details.items()])
        message += f" | {details_str}"
        
    logger.info(message)


def log_error_with_context(logger: logging.Logger, error: Exception,
                          context: Optional[Dict[str, Any]] = None):
    """
    Log an error with additional context information.
    
    Args:
        logger: Logger instance to use
        error: The exception that occurred
        context: Additional context as dictionary (optional)
    """
    message = f"ERROR: {type(error).__name__}: {str(error)}"
    
    if context:
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        message += f" | CONTEXT: {context_str}"
        
    logger.error(message, exc_info=True)


# Create module-level loggers
main_logger = setup_logger(__name__)
audit_logger = get_audit_logger()
performance_logger = get_performance_logger()

# Log system startup
main_logger.info("Logging system initialized successfully")
audit_logger.info("Audit logging started")
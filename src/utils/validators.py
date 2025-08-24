"""
Input validation utilities for CV Review Bot.

This module provides comprehensive validation functions for:
- GitHub repository URLs
- User inputs
- API responses
- Data integrity checks
"""

import re
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse
from utils.logger import setup_logger

# Initialize logger for this module
logger = setup_logger(__name__)


def validate_github_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if a URL is a valid GitHub repository URL.
    
    Checks for:
    - Proper URL format
    - GitHub domain (github.com)
    - Repository path structure (username/repository)
    
    Args:
        url: The URL string to validate
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
        - is_valid: True if URL is valid, False otherwise
        - error_message: Description of validation error if invalid
        
    Examples:
        >>> validate_github_url("https://github.com/user/repo")
        (True, None)
        
        >>> validate_github_url("https://gitlab.com/user/repo")
        (False, "URL must be from github.com")
    """
    logger.debug(f"Validating GitHub URL: {url}")
    
    # Check if URL is provided
    if not url or not isinstance(url, str):
        error_msg = "URL is required and must be a string"
        logger.warning(f"Validation failed: {error_msg}")
        return False, error_msg
    
    # Remove whitespace
    url = url.strip()
    
    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        error_msg = f"Invalid URL format: {str(e)}"
        logger.warning(f"URL parsing failed: {error_msg}")
        return False, error_msg
    
    # Check scheme (http or https)
    if parsed.scheme not in ['http', 'https']:
        error_msg = "URL must start with http:// or https://"
        logger.warning(f"Validation failed: {error_msg}")
        return False, error_msg
    
    # Check domain
    if parsed.netloc not in ['github.com', 'www.github.com']:
        error_msg = "URL must be from github.com"
        logger.warning(f"Validation failed: {error_msg}")
        return False, error_msg
    
    # Check path format (should be /username/repository)
    path_parts = [p for p in parsed.path.split('/') if p]
    
    if len(path_parts) < 2:
        error_msg = "URL must include username and repository name"
        logger.warning(f"Validation failed: {error_msg}")
        return False, error_msg
    
    # Validate username and repository name format
    username = path_parts[0]
    repo_name = path_parts[1]
    
    # GitHub username/repo naming rules
    username_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$'
    repo_pattern = r'^[a-zA-Z0-9._-]{1,100}$'
    
    if not re.match(username_pattern, username):
        error_msg = f"Invalid GitHub username format: {username}"
        logger.warning(f"Validation failed: {error_msg}")
        return False, error_msg
    
    if not re.match(repo_pattern, repo_name):
        error_msg = f"Invalid repository name format: {repo_name}"
        logger.warning(f"Validation failed: {error_msg}")
        return False, error_msg
    
    # Remove .git extension if present
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]
    
    logger.info(f"Successfully validated GitHub URL: {username}/{repo_name}")
    return True, None


def validate_role_selection(role: str) -> Tuple[bool, Optional[str]]:
    """
    Validate role selection for submission.
    
    Args:
        role: The role string to validate
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    valid_roles = ['backend', 'frontend']
    
    if not role:
        return False, "Role selection is required"
    
    role_lower = role.lower().strip()
    
    if role_lower not in valid_roles:
        return False, f"Invalid role. Must be one of: {', '.join(valid_roles)}"
    
    logger.debug(f"Valid role selected: {role_lower}")
    return True, None


def validate_telegram_user_id(user_id: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate Telegram user ID.
    
    Args:
        user_id: The user ID to validate
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if user_id is None:
        return False, "User ID is required"
    
    # Convert to string and check if it's numeric
    user_id_str = str(user_id)
    
    if not user_id_str.isdigit():
        return False, "Invalid user ID format"
    
    # Telegram user IDs are positive integers
    user_id_int = int(user_id_str)
    if user_id_int <= 0:
        return False, "User ID must be positive"
    
    logger.debug(f"Valid Telegram user ID: {user_id_str}")
    return True, None


def validate_analysis_result(result: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate LLM analysis result structure.
    
    Checks for required fields and proper format of analysis response.
    
    Args:
        result: The analysis result dictionary to validate
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not isinstance(result, dict):
        return False, "Analysis result must be a dictionary"
    
    # Required fields in analysis result
    required_fields = [
        'requirements_met',
        'scores',
        'recommendation',
        'confidence'
    ]
    
    # Check for required fields
    for field in required_fields:
        if field not in result:
            return False, f"Missing required field: {field}"
    
    # Validate scores structure
    if not isinstance(result.get('scores'), dict):
        return False, "Scores must be a dictionary"
    
    required_scores = ['completeness', 'quality', 'architecture', 'testing']
    for score in required_scores:
        if score not in result['scores']:
            return False, f"Missing score: {score}"
        
        # Validate score range (0-100)
        score_value = result['scores'][score]
        if not isinstance(score_value, (int, float)):
            return False, f"Score '{score}' must be numeric"
        if not 0 <= score_value <= 100:
            return False, f"Score '{score}' must be between 0 and 100"
    
    # Validate recommendation
    if result['recommendation'] not in ['ACCEPT', 'REJECT']:
        return False, "Recommendation must be either 'ACCEPT' or 'REJECT'"
    
    # Validate confidence
    confidence = result.get('confidence')
    if not isinstance(confidence, (int, float)):
        return False, "Confidence must be numeric"
    if not 0 <= confidence <= 100:
        return False, "Confidence must be between 0 and 100"
    
    logger.debug("Analysis result validation successful")
    return True, None


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input text.
    
    Removes potentially harmful characters and limits length.
    
    Args:
        text: The input text to sanitize
        max_length: Maximum allowed length (default: 1000)
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
    
    # Convert to string if not already
    text = str(text)
    
    # Remove control characters except newline and tab
    sanitized = ''.join(
        char for char in text 
        if char == '\n' or char == '\t' or not ord(char) < 32
    )
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
        logger.debug(f"Input truncated to {max_length} characters")
    
    return sanitized.strip()


def validate_repository_size(size_bytes: int) -> Tuple[bool, Optional[str]]:
    """
    Validate repository size against configured limits.
    
    Args:
        size_bytes: Repository size in bytes
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    from config import MAX_REPO_SIZE_MB
    
    max_size_bytes = MAX_REPO_SIZE_MB * 1024 * 1024
    
    if size_bytes <= 0:
        return False, "Invalid repository size"
    
    if size_bytes > max_size_bytes:
        size_mb = size_bytes / (1024 * 1024)
        return False, f"Repository too large: {size_mb:.2f}MB (max: {MAX_REPO_SIZE_MB}MB)"
    
    logger.debug(f"Repository size valid: {size_bytes / (1024 * 1024):.2f}MB")
    return True, None


def validate_env_variables() -> Tuple[bool, list]:
    """
    Validate that required environment variables are set.
    
    Returns:
        Tuple[bool, list]: (all_valid, missing_variables)
    """
    import os
    
    required_vars = ['BOT_TOKEN', 'OPENROUTER_KEY']
    missing = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            logger.error(f"Missing required environment variable: {var}")
    
    if missing:
        return False, missing
    
    logger.info("All required environment variables are set")
    return True, []


def validate_file_extension(filename: str, role: str) -> bool:
    """
    Check if file has a valid extension for the given role.
    
    Args:
        filename: Name of the file to check
        role: Role type ('backend' or 'frontend')
        
    Returns:
        bool: True if file extension is valid for the role
    """
    # Define valid extensions per role
    valid_extensions = {
        'backend': [
            '.go', '.mod', '.sum',  # Go files
            '.py', '.pyx',  # Python files
            '.java', '.kt',  # Java/Kotlin
            '.rs', '.toml',  # Rust
            '.md', '.txt', '.yml', '.yaml', '.json',  # Docs/Config
            'dockerfile', '.dockerignore'
        ],
        'frontend': [
            '.js', '.jsx', '.ts', '.tsx',  # JavaScript/TypeScript
            '.vue', '.svelte',  # Framework files
            '.html', '.css', '.scss', '.sass', '.less',  # Web files
            '.json', '.md', '.txt', '.yml', '.yaml',  # Config/Docs
            '.svg', '.png', '.jpg', '.jpeg', '.gif'  # Assets
        ]
    }
    
    # Get file extension
    filename_lower = filename.lower()
    
    # Check for files without extensions (like Dockerfile)
    if filename_lower in ['dockerfile', 'makefile', 'readme']:
        return True
    
    # Get the extension
    parts = filename_lower.split('.')
    if len(parts) > 1:
        ext = '.' + parts[-1]
        return ext in valid_extensions.get(role, [])
    
    return False


def validate_message_length(message: str, max_length: int = 4096) -> Tuple[bool, Optional[str]]:
    """
    Validate message length for Telegram constraints.
    
    Args:
        message: The message to validate
        max_length: Maximum allowed length (Telegram limit: 4096)
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not message:
        return False, "Message cannot be empty"
    
    if len(message) > max_length:
        return False, f"Message too long: {len(message)} characters (max: {max_length})"
    
    return True, None
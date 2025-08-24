"""
GitHub repository adapter implementation.

This module provides a GitHub-specific implementation of the RepositoryAdapter
interface, handling repository cloning, file extraction, and content optimization.
"""

import os
import re
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from pathlib import Path
import tiktoken
from git import Repo
from git.exc import GitCommandError
import time

from interfaces.repository import RepositoryAdapter
from core.models import RepositoryContent, FileInfo, Role
from core.exceptions import RepositoryError, ValidationError, TokenLimitError
from config import (
    MAX_REPO_SIZE_MB,
    CLONE_TIMEOUT,
    TEMP_DIR,
    BACKEND_PATTERNS,
    FRONTEND_PATTERNS,
    MAX_TOKENS
)
from utils.logger import setup_logger, log_performance, log_error_with_context

# Initialize logger for this module
logger = setup_logger(__name__)


class GitHubAdapter(RepositoryAdapter):
    """
    GitHub repository adapter implementation.
    
    This adapter handles fetching and processing GitHub repositories,
    including cloning, file extraction, token counting, and content optimization.
    
    Features:
    - Shallow cloning for performance
    - Role-based file prioritization
    - Token limit management
    - Smart file filtering
    - Automatic cleanup
    """
    
    # Supported GitHub URL patterns
    GITHUB_URL_PATTERNS = [
        r"^https://github\.com/[\w.-]+/[\w.-]+/?$",
        r"^git@github\.com:[\w.-]+/[\w.-]+\.git$",
        r"^https://github\.com/[\w.-]+/[\w.-]+\.git$"
    ]
    
    def __init__(self, max_tokens: int = MAX_TOKENS, temp_dir: str = TEMP_DIR):
        """
        Initialize the GitHub adapter.
        
        Args:
            max_tokens: Maximum token limit for LLM context
            temp_dir: Directory for temporary files
        """
        self.max_tokens = max_tokens
        self.temp_dir = temp_dir
        self._temp_directories = []  # Track for cleanup
        
        # Initialize token encoder for counting
        try:
            self.encoder = tiktoken.encoding_for_model("gpt-4")
        except Exception as e:
            logger.warning(f"Failed to load GPT-4 encoder, using cl100k_base: {e}")
            self.encoder = tiktoken.get_encoding("cl100k_base")
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)
        
        logger.info(f"GitHubAdapter initialized with max_tokens={max_tokens}")
    
    async def validate_url(self, url: str) -> bool:
        """
        Validate if the URL is a valid GitHub repository URL.
        
        Args:
            url: Repository URL to validate
            
        Returns:
            True if URL is valid GitHub URL, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
        
        # Check against supported patterns
        for pattern in self.GITHUB_URL_PATTERNS:
            if re.match(pattern, url.strip()):
                logger.debug(f"Valid GitHub URL: {url}")
                return True
        
        logger.debug(f"Invalid GitHub URL: {url}")
        return False
    
    @log_performance("github_repository_fetch")
    async def fetch_repository(self, url: str, role: Role) -> RepositoryContent:
        """
        Fetch and process repository content from GitHub.
        
        This method:
        1. Validates the URL
        2. Clones the repository
        3. Extracts relevant files based on role
        4. Calculates token counts
        5. Generates repository structure
        6. Optimizes content for LLM context
        
        Args:
            url: GitHub repository URL
            role: Role to optimize file selection for
            
        Returns:
            Processed repository content
            
        Raises:
            ValidationError: If URL is invalid
            RepositoryError: If fetching or processing fails
            TokenLimitError: If repository exceeds token limits
        """
        # Validate URL
        if not await self.validate_url(url):
            raise ValidationError(f"Invalid GitHub URL: {url}")
        
        temp_dir = None
        
        try:
            logger.info(f"Fetching GitHub repository: {url} for role: {role.value}")
            
            # Create temporary directory for cloning
            temp_dir = tempfile.mkdtemp(prefix='cv_review_github_', dir=self.temp_dir)
            self._temp_directories.append(temp_dir)
            logger.debug(f"Created temp directory: {temp_dir}")
            
            # Clone the repository
            repo = await self._clone_repository(url, temp_dir)
            if not repo:
                raise RepositoryError(f"Failed to clone repository: {url}")
            
            # Check repository size
            repo_size = self._get_directory_size(temp_dir)
            size_mb = repo_size / (1024 * 1024)
            logger.info(f"Repository size: {size_mb:.2f}MB")
            
            if repo_size > MAX_REPO_SIZE_MB * 1024 * 1024:
                logger.warning(f"Repository large: {size_mb:.2f}MB (max: {MAX_REPO_SIZE_MB}MB)")
                # Continue with processing but log warning
            
            # Extract relevant files based on role
            files = self._extract_files(temp_dir, role)
            logger.info(f"Extracted {len(files)} files from repository")
            
            if not files:
                raise RepositoryError(f"No relevant files found in repository: {url}")
            
            # Calculate total tokens before optimization
            raw_tokens = sum(file.tokens for file in files)
            logger.info(f"Raw content: {raw_tokens} tokens")
            
            # Generate repository structure
            structure = self._generate_repository_structure(files)
            
            # Get repository metadata
            metadata = await self._get_repository_metadata(url, temp_dir)
            
            # Create repository content object
            repo_content = RepositoryContent(
                url=url,
                files=files,
                total_tokens=raw_tokens,
                structure=structure,
                metadata=metadata
            )
            
            # Check token limits and optimize if necessary
            if raw_tokens > self.max_tokens:
                logger.warning(f"Repository exceeds token limit: {raw_tokens} > {self.max_tokens}")
                # Apply optimization to fit within limits
                repo_content = self._optimize_content_for_limits(repo_content)
            
            logger.info(f"Successfully processed repository: {len(repo_content.files)} files, "
                       f"{repo_content.total_tokens} tokens")
            
            return repo_content
            
        except (ValidationError, RepositoryError, TokenLimitError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            error_msg = f"Repository processing failed: {str(e)}"
            logger.error(error_msg)
            log_error_with_context(logger, e, {'url': url, 'role': role.value})
            raise RepositoryError(error_msg, details={'url': url, 'role': role.value})
    
    async def get_repository_info(self, url: str) -> Dict[str, Any]:
        """
        Get repository metadata without fetching content.
        
        Args:
            url: Repository URL
            
        Returns:
            Dictionary containing repository metadata
            
        Raises:
            ValidationError: If URL is invalid
            RepositoryError: If metadata fetching fails
        """
        if not await self.validate_url(url):
            raise ValidationError(f"Invalid GitHub URL: {url}")
        
        try:
            repo_id = self.extract_repo_id(url)
            
            # Basic info that can be extracted from URL
            parts = repo_id.split('/')
            owner = parts[0]
            name = parts[1]
            
            return {
                'name': name,
                'owner': owner,
                'full_name': repo_id,
                'platform': 'github.com',
                'url': url,
                'clone_url': self._normalize_clone_url(url)
            }
            
        except Exception as e:
            error_msg = f"Failed to get repository info: {str(e)}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, details={'url': url})
    
    def extract_repo_id(self, url: str) -> str:
        """
        Extract repository identifier from GitHub URL.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Repository identifier (e.g., "owner/repo")
            
        Raises:
            ValidationError: If URL format is invalid
        """
        if not url or not isinstance(url, str):
            raise ValidationError("URL cannot be empty")
        
        url = url.strip()
        
        # Handle different GitHub URL formats
        patterns = [
            r"^https://github\.com/([\w.-]+)/([\w.-]+)(?:\.git)?/?$",
            r"^git@github\.com:([\w.-]+)/([\w.-]+)(?:\.git)?$"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                owner, repo = match.groups()
                # Remove .git extension if present
                repo = repo.rstrip('.git')
                return f"{owner}/{repo}"
        
        raise ValidationError(f"Invalid GitHub URL format: {url}")
    
    async def cleanup(self) -> None:
        """
        Clean up temporary directories and resources.
        
        This method removes all temporary directories created during
        repository processing and clears internal state.
        """
        logger.debug(f"Cleaning up {len(self._temp_directories)} temporary directories")
        
        for temp_dir in self._temp_directories:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Removed temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp directory {temp_dir}: {e}")
        
        self._temp_directories.clear()
        logger.info("GitHub adapter cleanup completed")
    
    def get_supported_platforms(self) -> List[str]:
        """
        Get list of supported repository platforms.
        
        Returns:
            List of platform names
        """
        return ["github.com"]
    
    def get_file_patterns(self, role: Role) -> Dict[str, List[str]]:
        """
        Get file patterns to prioritize for a given role.
        
        Args:
            role: Role to get patterns for
            
        Returns:
            Dictionary with priority levels and file patterns
        """
        if role == Role.BACKEND:
            return BACKEND_PATTERNS.copy()
        elif role == Role.FRONTEND:
            return FRONTEND_PATTERNS.copy()
        else:
            logger.warning(f"Unknown role: {role}, using backend patterns")
            return BACKEND_PATTERNS.copy()
    
    # Private helper methods
    
    async def _clone_repository(self, url: str, target_dir: str) -> Optional[Repo]:
        """
        Clone a GitHub repository with timeout and error handling.
        
        Args:
            url: GitHub repository URL
            target_dir: Directory to clone into
            
        Returns:
            Git Repo object if successful, None otherwise
        """
        try:
            logger.info(f"Cloning repository: {url}")
            
            # Normalize URL for cloning
            clone_url = self._normalize_clone_url(url)
            
            # Use shallow clone for speed and bandwidth efficiency
            repo = Repo.clone_from(
                clone_url,
                target_dir,
                depth=1,  # Shallow clone - only latest commit
                single_branch=True,  # Only default branch
                progress=None,
                env={'GIT_TERMINAL_PROMPT': '0'}  # Disable password prompts
            )
            
            logger.info("Repository cloned successfully")
            return repo
            
        except GitCommandError as e:
            logger.error(f"Git command error during clone: {e}")
            return None
        except Exception as e:
            logger.error(f"Clone failed with error: {e}")
            return None
    
    def _normalize_clone_url(self, url: str) -> str:
        """
        Normalize URL for cloning (convert SSH to HTTPS if needed).
        
        Args:
            url: Original repository URL
            
        Returns:
            Normalized HTTPS URL for cloning
        """
        # Convert SSH URLs to HTTPS for better compatibility
        if url.startswith('git@github.com:'):
            # Convert git@github.com:owner/repo.git to https://github.com/owner/repo.git
            repo_path = url.replace('git@github.com:', '').replace('.git', '')
            return f"https://github.com/{repo_path}.git"
        
        # Ensure HTTPS URLs end with .git for consistency
        if url.startswith('https://github.com/') and not url.endswith('.git'):
            return f"{url.rstrip('/')}.git"
        
        return url
    
    def _extract_files(self, repo_path: str, role: Role) -> List[FileInfo]:
        """
        Extract relevant files from repository based on role patterns.
        
        Args:
            repo_path: Path to the cloned repository
            role: Role to determine file patterns
            
        Returns:
            List of FileInfo objects containing processed files
        """
        files = []
        repo_path = Path(repo_path)
        patterns = self.get_file_patterns(role)
        
        # Categorize files by priority for better organization
        critical_files = []
        important_files = []
        useful_files = []
        
        logger.debug(f"Extracting files from: {repo_path} for role: {role.value}")
        
        # Process each priority level
        for priority_level in ['critical', 'important', 'useful']:
            file_patterns = patterns.get(priority_level, [])
            
            for pattern in file_patterns:
                # Find matching files using glob pattern
                try:
                    for file_path in repo_path.glob(pattern):
                        if file_path.is_file() and not self._should_exclude_file(file_path, repo_path, patterns):
                            content = self._read_file_safely(file_path)
                            if content is not None:
                                # Detect programming language
                                language = self._detect_language(file_path)
                                
                                # Create FileInfo object
                                file_info = FileInfo(
                                    path=str(file_path.relative_to(repo_path)),
                                    content=content,
                                    priority=priority_level,
                                    tokens=self._count_tokens(content),
                                    language=language
                                )
                                
                                # Add to appropriate category
                                if priority_level == 'critical':
                                    critical_files.append(file_info)
                                elif priority_level == 'important':
                                    important_files.append(file_info)
                                else:
                                    useful_files.append(file_info)
                                    
                                logger.debug(f"Extracted file: {file_info.path} ({file_info.tokens} tokens)")
                                
                except Exception as e:
                    logger.warning(f"Error processing pattern '{pattern}': {e}")
                    continue
        
        # Combine files in priority order (critical first, then important, then useful)
        files = critical_files + important_files + useful_files
        
        # Remove duplicates (same file might match multiple patterns)
        seen_paths = set()
        unique_files = []
        for file_info in files:
            if file_info.path not in seen_paths:
                unique_files.append(file_info)
                seen_paths.add(file_info.path)
        
        logger.info(f"Extracted files - Critical: {len(critical_files)}, "
                   f"Important: {len(important_files)}, Useful: {len(useful_files)}, "
                   f"Total unique: {len(unique_files)}")
        
        return unique_files
    
    def _should_exclude_file(self, file_path: Path, repo_path: Path, patterns: Dict[str, List[str]]) -> bool:
        """
        Check if a file should be excluded based on exclusion patterns.
        
        Args:
            file_path: Path to the file
            repo_path: Root repository path
            patterns: Pattern dictionary containing exclude patterns
            
        Returns:
            True if file should be excluded, False otherwise
        """
        try:
            relative_path = str(file_path.relative_to(repo_path))
        except ValueError:
            # File is not under repo_path
            return True
        
        # Check exclusion patterns
        exclude_patterns = patterns.get('exclude', [])
        for exclude_pattern in exclude_patterns:
            # Simple pattern matching
            if self._matches_pattern(relative_path, exclude_pattern):
                logger.debug(f"Excluding file {relative_path} (matches pattern: {exclude_pattern})")
                return True
        
        return False
    
    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """
        Check if a file path matches a glob-like pattern.
        
        Args:
            file_path: File path to check
            pattern: Pattern to match against
            
        Returns:
            True if path matches pattern, False otherwise
        """
        # Simple pattern matching for common cases
        if '**' in pattern:
            # Handle recursive patterns
            pattern_part = pattern.replace('**/', '').replace('**', '')
            return pattern_part in file_path
        elif '*' in pattern:
            # Handle single-level wildcards
            import fnmatch
            return fnmatch.fnmatch(file_path, pattern)
        else:
            # Exact match or substring
            return pattern in file_path
    
    def _read_file_safely(self, file_path: Path, max_size: int = 1024 * 1024) -> Optional[str]:
        """
        Safely read a file with size limits and encoding detection.
        
        Args:
            file_path: Path to the file
            max_size: Maximum file size to read (default: 1MB)
            
        Returns:
            File content as string, or None if reading fails
        """
        try:
            # Check file size first
            file_size = file_path.stat().st_size
            if file_size > max_size:
                logger.warning(f"File too large ({file_size} bytes), skipping: {file_path}")
                return None
            
            if file_size == 0:
                logger.debug(f"Empty file, skipping: {file_path}")
                return None
            
            # Try different encodings in order of preference
            encodings = ['utf-8', 'utf-16', 'latin-1', 'ascii', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        content = f.read()
                        
                    # Basic validation that we got meaningful content
                    if content.strip():  # Not just whitespace
                        logger.debug(f"Successfully read file with {encoding}: {file_path}")
                        return content
                        
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    logger.debug(f"Error reading with {encoding}: {e}")
                    continue
            
            logger.warning(f"Could not decode file with any encoding: {file_path}")
            return None
            
        except Exception as e:
            logger.warning(f"Error reading file {file_path}: {e}")
            return None
    
    def _detect_language(self, file_path: Path) -> Optional[str]:
        """
        Detect programming language based on file extension.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Programming language name or None if unknown
        """
        suffix = file_path.suffix.lower()
        
        # Language mapping based on common extensions
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.rs': 'rust',
            '.kt': 'kotlin',
            '.swift': 'swift',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.md': 'markdown',
            '.sql': 'sql',
            '.sh': 'bash',
            '.dockerfile': 'dockerfile'
        }
        
        # Special case for files without extension
        if not suffix:
            filename = file_path.name.lower()
            if filename in ['dockerfile', 'makefile', 'rakefile']:
                return filename
            elif filename.startswith('.'):
                # Config files
                return 'config'
        
        return language_map.get(suffix)
    
    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using tiktoken.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
            
        try:
            return len(self.encoder.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            # Fallback: estimate 1 token per 4 characters (rough approximation)
            return len(text) // 4
    
    def _generate_repository_structure(self, files: List[FileInfo]) -> str:
        """
        Generate a tree structure representation of the repository.
        
        Args:
            files: List of FileInfo objects
            
        Returns:
            Tree structure as string
        """
        if not files:
            return "No files found"
        
        # Build directory tree structure
        tree_lines = ["Repository Structure:"]
        tree_lines.append("")
        
        # Organize files by directory
        directories = {}
        root_files = []
        
        for file_info in files:
            path_parts = file_info.path.split('/')
            if len(path_parts) == 1:
                # Root level file
                root_files.append(file_info)
            else:
                # File in subdirectory
                dir_path = '/'.join(path_parts[:-1])
                filename = path_parts[-1]
                
                if dir_path not in directories:
                    directories[dir_path] = []
                directories[dir_path].append((filename, file_info))
        
        # Add root files first
        for file_info in sorted(root_files, key=lambda f: f.path):
            priority_marker = self._get_priority_marker(file_info.priority)
            tree_lines.append(f"├── {file_info.path} {priority_marker}")
        
        # Add directories and their files
        for dir_path in sorted(directories.keys()):
            tree_lines.append(f"├── {dir_path}/")
            
            files_in_dir = sorted(directories[dir_path], key=lambda x: x[0])
            for i, (filename, file_info) in enumerate(files_in_dir):
                is_last = i == len(files_in_dir) - 1
                prefix = "└──" if is_last else "├──"
                priority_marker = self._get_priority_marker(file_info.priority)
                tree_lines.append(f"│   {prefix} {filename} {priority_marker}")
        
        # Add summary
        tree_lines.append("")
        critical_count = len([f for f in files if f.priority == 'critical'])
        important_count = len([f for f in files if f.priority == 'important'])
        useful_count = len([f for f in files if f.priority == 'useful'])
        total_tokens = sum(f.tokens for f in files)
        
        tree_lines.append(f"Files: {len(files)} total")
        tree_lines.append(f"  • Critical: {critical_count}")
        tree_lines.append(f"  • Important: {important_count}")
        tree_lines.append(f"  • Useful: {useful_count}")
        tree_lines.append(f"Tokens: {total_tokens:,}")
        
        return '\n'.join(tree_lines)
    
    def _get_priority_marker(self, priority: str) -> str:
        """
        Get a visual marker for file priority.
        
        Args:
            priority: Priority level string
            
        Returns:
            Visual marker string
        """
        markers = {
            'critical': '[🔥]',
            'important': '[⭐]',
            'useful': '[📄]'
        }
        return markers.get(priority, '[📄]')
    
    def _get_directory_size(self, path: str) -> int:
        """
        Calculate total size of directory in bytes.
        
        Args:
            path: Directory path
            
        Returns:
            Total size in bytes
        """
        total_size = 0
        
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        # Skip files we can't read
                        continue
        except Exception as e:
            logger.warning(f"Error calculating directory size: {e}")
        
        return total_size
    
    async def _get_repository_metadata(self, url: str, repo_path: str) -> Dict[str, Any]:
        """
        Extract repository metadata from URL and local clone.
        
        Args:
            url: Repository URL
            repo_path: Path to cloned repository
            
        Returns:
            Dictionary containing metadata
        """
        metadata = {}
        
        try:
            # Extract basic info from URL
            repo_id = self.extract_repo_id(url)
            parts = repo_id.split('/')
            metadata['owner'] = parts[0]
            metadata['name'] = parts[1]
            metadata['full_name'] = repo_id
            metadata['platform'] = 'github.com'
            
            # Get repository size
            repo_size = self._get_directory_size(repo_path)
            metadata['size_bytes'] = repo_size
            metadata['size_mb'] = round(repo_size / (1024 * 1024), 2)
            
            # Try to get additional info from .git if available
            try:
                git_dir = os.path.join(repo_path, '.git')
                if os.path.exists(git_dir):
                    repo = Repo(repo_path)
                    if repo.head.is_valid():
                        latest_commit = repo.head.commit
                        metadata['latest_commit'] = {
                            'sha': latest_commit.hexsha[:8],
                            'message': latest_commit.message.strip(),
                            'author': str(latest_commit.author),
                            'date': latest_commit.committed_datetime.isoformat()
                        }
                        
                        # Get branch info
                        try:
                            metadata['default_branch'] = repo.active_branch.name
                        except Exception:
                            metadata['default_branch'] = 'unknown'
            except Exception as e:
                logger.debug(f"Could not extract git metadata: {e}")
            
            # Try to read README for description
            readme_files = ['README.md', 'README.txt', 'README', 'readme.md']
            for readme_file in readme_files:
                readme_path = os.path.join(repo_path, readme_file)
                if os.path.exists(readme_path):
                    try:
                        with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(500)  # First 500 chars
                            if content.strip():
                                metadata['description'] = content.strip()
                                break
                    except Exception:
                        continue
            
        except Exception as e:
            logger.warning(f"Error extracting repository metadata: {e}")
        
        return metadata
    
    def _optimize_content_for_limits(self, repo_content: RepositoryContent) -> RepositoryContent:
        """
        Optimize repository content to fit within token limits.
        
        This method prioritizes files and truncates content as needed while
        preserving the most important code for analysis.
        
        Args:
            repo_content: Original repository content
            
        Returns:
            Optimized repository content within limits
        """
        logger.info(f"Optimizing content from {repo_content.total_tokens} to max {self.max_tokens} tokens")
        
        # Reserve tokens for structure and metadata
        reserved_tokens = 2000
        available_tokens = self.max_tokens - reserved_tokens
        
        if available_tokens <= 0:
            raise TokenLimitError(
                f"Token limit too low: {self.max_tokens} (need at least {reserved_tokens} for structure)",
                repo_content.total_tokens,
                self.max_tokens
            )
        
        # Sort files by priority and include as many as possible
        priority_order = {'critical': 0, 'important': 1, 'useful': 2}
        sorted_files = sorted(
            repo_content.files,
            key=lambda f: (priority_order.get(f.priority, 3), f.tokens)
        )
        
        optimized_files = []
        current_tokens = 0
        
        for file_info in sorted_files:
            if current_tokens + file_info.tokens <= available_tokens:
                # Include entire file
                optimized_files.append(file_info)
                current_tokens += file_info.tokens
            elif file_info.priority == 'critical' and current_tokens < available_tokens:
                # For critical files, try to include partial content
                remaining_tokens = available_tokens - current_tokens
                if remaining_tokens > 100:  # Only if meaningful amount remaining
                    truncated_content = self._truncate_to_tokens(file_info.content, remaining_tokens)
                    if truncated_content:
                        truncated_file = FileInfo(
                            path=f"{file_info.path} [TRUNCATED]",
                            content=truncated_content,
                            priority=file_info.priority,
                            tokens=remaining_tokens,
                            language=file_info.language
                        )
                        optimized_files.append(truncated_file)
                        current_tokens += remaining_tokens
                        logger.info(f"Truncated critical file: {file_info.path}")
                break
            else:
                # Skip remaining files
                logger.info(f"Skipping remaining files due to token limit")
                break
        
        # Update repository content
        optimized_content = RepositoryContent(
            url=repo_content.url,
            files=optimized_files,
            total_tokens=current_tokens,
            structure=self._generate_repository_structure(optimized_files),
            metadata=repo_content.metadata
        )
        
        skipped_count = len(repo_content.files) - len(optimized_files)
        logger.info(f"Optimization complete: kept {len(optimized_files)} files, "
                   f"skipped {skipped_count} files, using {current_tokens} tokens")
        
        return optimized_content
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens
            
        Returns:
            Truncated text
        """
        if not text or max_tokens <= 0:
            return ""
            
        try:
            tokens = self.encoder.encode(text)
            if len(tokens) <= max_tokens:
                return text
            
            # Truncate tokens and decode back to text
            truncated_tokens = tokens[:max_tokens]
            truncated_text = self.encoder.decode(truncated_tokens)
            
            # Add truncation indicator
            return truncated_text + "\n\n[...TRUNCATED...]\n"
            
        except Exception as e:
            logger.warning(f"Token truncation failed: {e}")
            # Fallback: character-based truncation (rough approximation)
            estimated_chars = max_tokens * 3  # Conservative estimate
            if len(text) <= estimated_chars:
                return text
            return text[:estimated_chars] + "\n\n[...TRUNCATED...]\n"
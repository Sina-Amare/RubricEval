"""
Tests for utility modules.

This module tests various utility functions including:
- URL validation
- Token counting
- Input sanitization
- File extension validation
"""

import pytest
from utils.validators import (
    validate_github_url, extract_github_info, validate_role_selection,
    validate_telegram_user_id, validate_analysis_result, sanitize_input,
    validate_repository_size, validate_env_variables, validate_file_extension,
    validate_message_length
)
from utils.token_counter import TokenCounter, estimate_tokens, can_fit_model_context


@pytest.mark.unit
class TestGitHubValidation:
    """Test GitHub URL validation and parsing."""
    
    def test_valid_github_urls(self):
        """Test valid GitHub URL formats."""
        valid_urls = [
            "https://github.com/user/repo",
            "https://github.com/user/repo.git",
            "https://github.com/user/my-repo-name",
            "https://github.com/user123/repo_name",
            "https://github.com/user/repo/tree/main",
            "https://github.com/user/repo/tree/feature/branch",
            "https://www.github.com/user/repo",
            "http://github.com/user/repo",
        ]
        
        for url in valid_urls:
            is_valid, error = validate_github_url(url)
            assert is_valid, f"URL {url} should be valid but got error: {error}"
    
    def test_invalid_github_urls(self):
        """Test invalid GitHub URL formats."""
        invalid_urls = [
            "https://gitlab.com/user/repo",  # Wrong domain
            "https://github.com/user",       # Missing repo
            "https://github.com/",           # Missing user and repo
            "github.com/user/repo",          # Missing protocol
            "https://github.com/user/repo with spaces",  # Invalid characters
            "",                              # Empty URL
            None,                           # None value
            "https://github.com/user$/repo", # Invalid username
            "https://github.com/user/repo<script>", # Invalid repo name
        ]
        
        for url in invalid_urls:
            is_valid, error = validate_github_url(url)
            assert not is_valid, f"URL {url} should be invalid but was accepted"
            assert error is not None, f"Expected error message for invalid URL: {url}"
    
    def test_extract_github_info_basic(self):
        """Test basic GitHub info extraction."""
        username, repo_name, branch = extract_github_info("https://github.com/user/repo")
        
        assert username == "user"
        assert repo_name == "repo"
        assert branch is None
    
    def test_extract_github_info_with_git_extension(self):
        """Test GitHub info extraction with .git extension."""
        username, repo_name, branch = extract_github_info("https://github.com/user/repo.git")
        
        assert username == "user"
        assert repo_name == "repo"  # .git should be removed
        assert branch is None
    
    def test_extract_github_info_with_branch(self):
        """Test GitHub info extraction with branch."""
        username, repo_name, branch = extract_github_info("https://github.com/user/repo/tree/develop")
        
        assert username == "user"
        assert repo_name == "repo"
        assert branch == "develop"
    
    def test_extract_github_info_with_nested_branch(self):
        """Test GitHub info extraction with nested branch path."""
        username, repo_name, branch = extract_github_info("https://github.com/user/repo/tree/feature/new-auth")
        
        assert username == "user"
        assert repo_name == "repo"
        assert branch == "feature/new-auth"


@pytest.mark.unit
class TestInputValidation:
    """Test input validation functions."""
    
    def test_validate_role_selection_valid(self):
        """Test valid role selections."""
        valid_roles = ["backend", "frontend", "Backend", "Frontend", "BACKEND", "FRONTEND", "  backend  "]
        
        for role in valid_roles:
            is_valid, error = validate_role_selection(role)
            assert is_valid, f"Role {role} should be valid but got error: {error}"
    
    def test_validate_role_selection_invalid(self):
        """Test invalid role selections."""
        invalid_roles = ["", None, "fullstack", "devops", "mobile", 123]
        
        for role in invalid_roles:
            is_valid, error = validate_role_selection(role)
            assert not is_valid, f"Role {role} should be invalid but was accepted"
    
    def test_validate_telegram_user_id_valid(self):
        """Test valid Telegram user IDs."""
        valid_ids = [123456789, "123456789", "1", "999999999999"]
        
        for user_id in valid_ids:
            is_valid, error = validate_telegram_user_id(user_id)
            assert is_valid, f"User ID {user_id} should be valid but got error: {error}"
    
    def test_validate_telegram_user_id_invalid(self):
        """Test invalid Telegram user IDs."""
        invalid_ids = [None, "", "abc123", "-123", 0, -1, "0", 0.5]
        
        for user_id in invalid_ids:
            is_valid, error = validate_telegram_user_id(user_id)
            assert not is_valid, f"User ID {user_id} should be invalid but was accepted"
    
    def test_sanitize_input_basic(self):
        """Test basic input sanitization."""
        # Normal text should pass through unchanged
        result = sanitize_input("Hello, World!")
        assert result == "Hello, World!"
        
        # Empty input
        result = sanitize_input("")
        assert result == ""
        
        # None input
        result = sanitize_input(None)
        assert result == ""
    
    def test_sanitize_input_control_characters(self):
        """Test sanitization of control characters."""
        # Control characters should be removed except newline and tab
        input_text = "Hello\x00\x01\x02World\nNew line\tTab"
        result = sanitize_input(input_text)
        assert result == "HelloWorld\nNew line\tTab"
    
    def test_sanitize_input_length_limit(self):
        """Test input length limiting."""
        long_text = "A" * 2000
        result = sanitize_input(long_text, max_length=100)
        assert len(result) == 100
        assert result == "A" * 100
    
    def test_validate_repository_size(self, mock_env_vars):
        """Test repository size validation."""
        # Valid size (under limit)
        is_valid, error = validate_repository_size(10 * 1024 * 1024)  # 10MB
        assert is_valid
        assert error is None
        
        # Invalid size (over limit) - using 50MB from mock_env_vars
        is_valid, error = validate_repository_size(100 * 1024 * 1024)  # 100MB
        assert not is_valid
        assert "too large" in error.lower()
        
        # Invalid size (zero or negative)
        is_valid, error = validate_repository_size(0)
        assert not is_valid
        assert "invalid" in error.lower()
    
    def test_validate_file_extension_backend(self):
        """Test file extension validation for backend role."""
        # Valid backend extensions
        valid_files = [
            "main.go", "go.mod", "app.py", "server.java", "main.rs",
            "README.md", "config.yml", "docker-compose.yaml", "Dockerfile"
        ]
        
        for filename in valid_files:
            is_valid = validate_file_extension(filename, "backend")
            assert is_valid, f"File {filename} should be valid for backend role"
        
        # Invalid backend extensions
        invalid_files = [
            "app.js", "component.tsx", "style.css", "image.png", "video.mp4"
        ]
        
        for filename in invalid_files:
            is_valid = validate_file_extension(filename, "backend")
            assert not is_valid, f"File {filename} should not be valid for backend role"
    
    def test_validate_file_extension_frontend(self):
        """Test file extension validation for frontend role."""
        # Valid frontend extensions
        valid_files = [
            "app.js", "component.jsx", "page.tsx", "style.css", "config.json",
            "index.html", "component.vue", "README.md", "package.json"
        ]
        
        for filename in valid_files:
            is_valid = validate_file_extension(filename, "frontend")
            assert is_valid, f"File {filename} should be valid for frontend role"
        
        # Invalid frontend extensions
        invalid_files = [
            "main.go", "server.py", "app.java", "main.rs", "binary.exe"
        ]
        
        for filename in invalid_files:
            is_valid = validate_file_extension(filename, "frontend")
            assert not is_valid, f"File {filename} should not be valid for frontend role"
    
    def test_validate_message_length(self):
        """Test message length validation for Telegram."""
        # Valid message
        is_valid, error = validate_message_length("Hello, World!")
        assert is_valid
        assert error is None
        
        # Empty message
        is_valid, error = validate_message_length("")
        assert not is_valid
        assert "empty" in error.lower()
        
        # Too long message
        long_message = "A" * 5000
        is_valid, error = validate_message_length(long_message)
        assert not is_valid
        assert "too long" in error.lower()


@pytest.mark.unit
class TestAnalysisResultValidation:
    """Test analysis result validation."""
    
    def test_validate_analysis_result_valid_old_format(self):
        """Test validation of valid analysis result (old format)."""
        valid_result = {
            "requirements_met": {
                "architectural_pattern": True,
                "repository_pattern": False
            },
            "scores": {
                "task_completion": 80,
                "code_quality": 75,
                "architecture": 70,
                "testing": 65
            },
            "recommendation": "yes",
            "confidence": 85,
            "strengths": ["Good structure", "Clean code"],
            "weaknesses": ["Missing tests", "No documentation"],
            "detailed_feedback": "The code is well-structured..."
        }
        
        is_valid, error = validate_analysis_result(valid_result)
        assert is_valid
        assert error is None
    
    def test_validate_analysis_result_valid_new_format(self):
        """Test validation of valid analysis result (new format)."""
        valid_result = {
            "task_analysis": {
                "requirements_completeness": 0.8
            },
            "requirements_implementation": {
                "architectural_pattern": {"implemented": True},
                "repository_pattern": {"implemented": False}
            },
            "scores": {
                "task_completion": 80,
                "code_quality": 75
            },
            "recommendation": "yes", 
            "confidence": 85
        }
        
        is_valid, error = validate_analysis_result(valid_result)
        assert is_valid
        assert error is None
    
    def test_validate_analysis_result_missing_required_fields(self):
        """Test validation with missing required fields."""
        # Missing scores
        invalid_result = {
            "requirements_met": {},
            "recommendation": "yes",
            "confidence": 85
        }
        
        is_valid, error = validate_analysis_result(invalid_result)
        assert not is_valid
        assert "missing required field" in error.lower()
    
    def test_validate_analysis_result_invalid_scores(self):
        """Test validation with invalid score values."""
        # Scores out of range
        invalid_result = {
            "requirements_met": {},
            "scores": {
                "task_completion": 150,  # Over 100
                "code_quality": -10      # Under 0
            },
            "recommendation": "yes",
            "confidence": 85
        }
        
        is_valid, error = validate_analysis_result(invalid_result)
        assert not is_valid
        assert "between 0 and 100" in error
    
    def test_validate_analysis_result_invalid_confidence(self):
        """Test validation with invalid confidence value."""
        invalid_result = {
            "requirements_met": {},
            "scores": {"quality": 80},
            "recommendation": "yes",
            "confidence": 150  # Over 100
        }
        
        is_valid, error = validate_analysis_result(invalid_result)
        assert not is_valid
        assert "confidence" in error.lower()
    
    def test_validate_analysis_result_penalty_scores(self):
        """Test validation allows penalty scores above 100."""
        result_with_penalty = {
            "requirements_met": {},
            "scores": {
                "task_completion": 80,
                "critical_issues_penalty": 120  # Penalty can exceed 100
            },
            "recommendation": "no",
            "confidence": 70
        }
        
        is_valid, error = validate_analysis_result(result_with_penalty)
        assert is_valid
        assert error is None


@pytest.mark.unit
class TestTokenCounter:
    """Test token counting utilities."""
    
    def test_estimate_tokens_basic(self):
        """Test basic token estimation."""
        text = "Hello, world! This is a test."
        tokens = TokenCounter.estimate_tokens(text)
        
        # Should return a reasonable token count (not exact, but in ballpark)
        assert tokens > 0
        assert tokens < len(text)  # Should be less than character count
    
    def test_estimate_tokens_different_models(self):
        """Test token estimation for different model families."""
        text = "This is a sample text for token counting."
        
        gpt_tokens = TokenCounter.estimate_tokens(text, "gpt")
        claude_tokens = TokenCounter.estimate_tokens(text, "claude")
        gemini_tokens = TokenCounter.estimate_tokens(text, "gemini")
        default_tokens = TokenCounter.estimate_tokens(text, "default")
        
        # All should return positive values
        assert gpt_tokens > 0
        assert claude_tokens > 0
        assert gemini_tokens > 0
        assert default_tokens > 0
        
        # Claude should give slightly more tokens (lower chars per token)
        assert claude_tokens >= gpt_tokens
    
    def test_estimate_tokens_empty_text(self):
        """Test token estimation with empty text."""
        assert TokenCounter.estimate_tokens("") == 0
        assert TokenCounter.estimate_tokens(None) == 0
    
    def test_estimate_prompt_tokens(self):
        """Test prompt token estimation with system and user messages."""
        system_prompt = "You are a helpful assistant."
        user_prompt = "Analyze this code for quality."
        
        token_info = TokenCounter.estimate_prompt_tokens(system_prompt, user_prompt)
        
        assert "system_tokens" in token_info
        assert "user_tokens" in token_info
        assert "total_tokens" in token_info
        assert "formatting_overhead" in token_info
        
        # Total should be sum of parts
        expected_total = (token_info["system_tokens"] + 
                         token_info["user_tokens"] + 
                         token_info["formatting_overhead"])
        assert token_info["total_tokens"] == expected_total
    
    def test_can_fit_context(self):
        """Test context window fitting check."""
        short_text = "Short text"
        long_text = "A" * 10000
        
        # Short text should fit in small context
        assert TokenCounter.can_fit_context(short_text, 1000)
        
        # Long text should not fit in small context
        assert not TokenCounter.can_fit_context(long_text, 100)
    
    def test_get_model_family(self):
        """Test model family detection."""
        assert TokenCounter.get_model_family("gpt-4") == "gpt"
        assert TokenCounter.get_model_family("openai/gpt-3.5-turbo") == "gpt"
        assert TokenCounter.get_model_family("claude-3") == "claude"
        assert TokenCounter.get_model_family("anthropic/claude") == "claude"
        assert TokenCounter.get_model_family("gemini-pro") == "gemini"
        assert TokenCounter.get_model_family("google/gemini") == "gemini"
        assert TokenCounter.get_model_family("unknown-model") == "default"
    
    def test_truncate_to_fit(self):
        """Test text truncation to fit context."""
        long_text = "This is a very long text. " * 100
        
        # Should return original if it fits
        short_result = TokenCounter.truncate_to_fit("Short text", 1000)
        assert short_result == "Short text"
        
        # Should truncate if too long
        truncated = TokenCounter.truncate_to_fit(long_text, 100)
        assert len(truncated) < len(long_text)
        assert "Content truncated" in truncated
    
    def test_convenience_functions(self):
        """Test convenience wrapper functions."""
        text = "Test text for token counting"
        
        # Test estimate_tokens function
        tokens = estimate_tokens(text)
        assert tokens > 0
        
        # Test with model name
        tokens_with_model = estimate_tokens(text, "gpt-4")
        assert tokens_with_model > 0
        
        # Test can_fit_model_context function
        assert can_fit_model_context("Short", "gpt-4", 1000)
        assert not can_fit_model_context("A" * 10000, "gpt-4", 100)


@pytest.mark.unit
class TestEnvironmentValidation:
    """Test environment variable validation."""
    
    def test_validate_env_variables_with_mock(self, mock_env_vars):
        """Test environment validation with mocked variables."""
        # Should pass with mocked environment
        all_valid, missing = validate_env_variables()
        assert all_valid
        assert missing == []
    
    def test_validate_env_variables_missing(self, monkeypatch):
        """Test environment validation with missing variables."""
        # Remove required env vars
        monkeypatch.delenv("BOT_TOKEN", raising=False)
        monkeypatch.delenv("OPENROUTER_KEY", raising=False)
        
        all_valid, missing = validate_env_variables()
        assert not all_valid
        assert "BOT_TOKEN" in missing
        assert "OPENROUTER_KEY" in missing


@pytest.mark.unit
class TestValidationEdgeCases:
    """Test edge cases and error conditions in validation."""
    
    def test_validate_github_url_edge_cases(self):
        """Test GitHub URL validation edge cases."""
        # URL with unusual but valid characters
        is_valid, _ = validate_github_url("https://github.com/user-123/repo_name.test")
        assert is_valid
        
        # URL with maximum length username (39 chars is GitHub limit)
        long_username = "a" + "b" * 37 + "c"  # 39 chars total
        is_valid, _ = validate_github_url(f"https://github.com/{long_username}/repo")
        assert is_valid
        
        # URL with too long username (40+ chars)
        too_long_username = "a" * 40
        is_valid, _ = validate_github_url(f"https://github.com/{too_long_username}/repo")
        assert not is_valid
    
    def test_sanitize_input_type_conversion(self):
        """Test input sanitization with different input types."""
        # Integer input
        result = sanitize_input(12345)
        assert result == "12345"
        
        # Float input
        result = sanitize_input(123.45)
        assert result == "123.45"
        
        # Boolean input
        result = sanitize_input(True)
        assert result == "True"
    
    def test_validate_analysis_result_type_errors(self):
        """Test analysis result validation with type errors."""
        # Non-dictionary input
        is_valid, error = validate_analysis_result("not a dict")
        assert not is_valid
        assert "dictionary" in error.lower()
        
        # Scores as non-dictionary
        invalid_result = {
            "requirements_met": {},
            "scores": "not a dict",
            "recommendation": "yes",
            "confidence": 85
        }
        
        is_valid, error = validate_analysis_result(invalid_result)
        assert not is_valid
        assert "scores" in error.lower() and "dictionary" in error.lower()
    
    def test_token_counter_edge_cases(self):
        """Test token counter edge cases."""
        # Very long text
        very_long_text = "word " * 10000
        tokens = TokenCounter.estimate_tokens(very_long_text)
        assert tokens > 1000  # Should handle long text
        
        # Text with special characters
        special_text = "Hello! @#$%^&*()_+-={}[]|\\:;\"'<>?,./"
        tokens = TokenCounter.estimate_tokens(special_text)
        assert tokens > 0
        
        # Unicode text
        unicode_text = "Hello 世界 café naïve résumé"
        tokens = TokenCounter.estimate_tokens(unicode_text)
        assert tokens > 0

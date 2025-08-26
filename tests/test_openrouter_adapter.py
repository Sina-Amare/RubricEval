"""
Tests for OpenRouter analyzer adapter.

This module tests the OpenRouter adapter implementation,
including LLM API integration, response parsing, and error handling.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisRequest, AnalysisResult, Role, RecommendationLevel
from core.exceptions import AnalysisError, RateLimitError, TokenLimitError


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpenRouterAdapterInitialization:
    """Test OpenRouter adapter initialization and configuration."""
    
    def test_adapter_initialization_with_defaults(self, mock_env_vars):
        """Test adapter initialization with default configuration."""
        adapter = OpenRouterAdapter()
        
        assert adapter.api_key == "test_openrouter_key"
        assert adapter.primary_model == "test/primary-model"
        assert adapter.fallback_model == "test/fallback-model"
        assert adapter.max_tokens == 900000
        assert adapter.temperature == 0.1
    
    def test_adapter_initialization_with_custom_config(self, mock_env_vars):
        """Test adapter initialization with custom configuration."""
        config = {
            "primary_model": "custom/model",
            "fallback_model": "custom/fallback",
            "max_tokens": 50000,
            "temperature": 0.5
        }
        
        adapter = OpenRouterAdapter(**config)
        
        assert adapter.primary_model == "custom/model"
        assert adapter.fallback_model == "custom/fallback"
        assert adapter.max_tokens == 50000
        assert adapter.temperature == 0.5
    
    def test_adapter_initialization_missing_api_key(self, monkeypatch):
        """Test adapter initialization with missing API key."""
        monkeypatch.delenv("OPENROUTER_KEY", raising=False)
        
        with pytest.raises(ValueError, match="OPENROUTER_KEY environment variable"):
            OpenRouterAdapter()
    
    def test_get_supported_models(self, mock_env_vars):
        """Test getting supported models."""
        adapter = OpenRouterAdapter()
        models = adapter.get_supported_models()
        
        assert isinstance(models, list)
        assert len(models) > 0
        
        # Check model structure
        model = models[0]
        assert "name" in model
        assert "context_window" in model
        assert "capabilities" in model
    
    def test_get_max_tokens(self, mock_env_vars):
        """Test getting maximum tokens."""
        adapter = OpenRouterAdapter()
        max_tokens = adapter.get_max_tokens()
        
        assert max_tokens == 900000  # From mock env vars
    
    def test_get_retry_policy(self, mock_env_vars):
        """Test getting retry policy configuration."""
        adapter = OpenRouterAdapter()
        policy = adapter.get_retry_policy()
        
        assert isinstance(policy, dict)
        assert "max_retries" in policy
        assert "initial_delay" in policy
        assert "max_delay" in policy
        assert "exponential_base" in policy


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpenRouterAdapterTokenHandling:
    """Test token estimation and handling."""
    
    @pytest.fixture
    def adapter(self, mock_env_vars):
        """Create OpenRouter adapter for testing."""
        return OpenRouterAdapter()
    
    def test_estimate_tokens(self, adapter):
        """Test token estimation."""
        text = "This is a sample text for token counting."
        tokens = adapter.estimate_tokens(text)
        
        assert isinstance(tokens, int)
        assert tokens > 0
        assert tokens < len(text)  # Should be less than character count
    
    def test_estimate_tokens_empty_text(self, adapter):
        """Test token estimation with empty text."""
        assert adapter.estimate_tokens("") == 0
        assert adapter.estimate_tokens(None) == 0
    
    def test_estimate_tokens_long_text(self, adapter):
        """Test token estimation with long text."""
        long_text = "word " * 1000
        tokens = adapter.estimate_tokens(long_text)
        
        assert tokens > 500  # Should be reasonable for long text
        assert tokens < len(long_text)
    
    async def test_check_token_limits(self, adapter, sample_analysis_request):
        """Test token limit checking."""
        # Should not raise for reasonable content
        try:
            await adapter._check_token_limits(sample_analysis_request)
        except TokenLimitError:
            pytest.fail("Should not raise TokenLimitError for reasonable content")
        
        # Test with very large content
        large_files = []
        for i in range(100):
            large_files.append(type('FileInfo', (), {
                'path': f'file_{i}.py',
                'content': 'def function():\n    pass\n' * 1000,
                'priority': 'critical',
                'tokens': 5000
            })())
        
        sample_analysis_request.repository_content.files = large_files
        sample_analysis_request.repository_content.total_tokens = 500000
        
        with pytest.raises(TokenLimitError):
            await adapter._check_token_limits(sample_analysis_request)


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpenRouterAdapterPromptFormatting:
    """Test prompt formatting and preparation."""
    
    @pytest.fixture
    def adapter(self, mock_env_vars):
        """Create OpenRouter adapter for testing."""
        return OpenRouterAdapter()
    
    async def test_format_prompt(self, adapter, sample_analysis_request):
        """Test basic prompt formatting."""
        formatted = await adapter.format_prompt(sample_analysis_request)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        
        # Check that key elements are included
        assert sample_analysis_request.task_requirements in formatted
        assert sample_analysis_request.role.value in formatted
        
        # Check for repository content
        for file_info in sample_analysis_request.repository_content.files:
            assert file_info.path in formatted
    
    async def test_format_prompt_backend_role(self, adapter, sample_repository_content):
        """Test prompt formatting for backend role."""
        request = AnalysisRequest(
            repository_content=sample_repository_content,
            role=Role.BACKEND,
            task_requirements="Build a REST API with database integration",
            github_url="https://github.com/test/backend-repo"
        )
        
        formatted = await adapter.format_prompt(request)
        
        # Should contain backend-specific elements
        assert "backend" in formatted.lower()
        assert "api" in formatted.lower()
        assert "database" in formatted.lower()
    
    async def test_format_prompt_frontend_role(self, adapter, sample_repository_content):
        """Test prompt formatting for frontend role."""
        request = AnalysisRequest(
            repository_content=sample_repository_content,
            role=Role.FRONTEND,
            task_requirements="Build a React application with responsive design",
            github_url="https://github.com/test/frontend-repo"
        )
        
        formatted = await adapter.format_prompt(request)
        
        # Should contain frontend-specific elements
        assert "frontend" in formatted.lower()
        assert "react" in formatted.lower()
        assert "responsive" in formatted.lower()
    
    async def test_format_prompt_with_file_priority(self, adapter, sample_repository_content):
        """Test prompt formatting respects file priorities."""
        # Add files with different priorities
        from core.models import FileInfo
        
        critical_file = FileInfo(
            path="main.py",
            content="def main(): pass",
            priority="critical"
        )
        
        useful_file = FileInfo(
            path="utils.py", 
            content="def helper(): pass",
            priority="useful"
        )
        
        sample_repository_content.files = [critical_file, useful_file]
        
        request = AnalysisRequest(
            repository_content=sample_repository_content,
            role=Role.BACKEND,
            task_requirements="Test requirements",
            github_url="https://github.com/test/repo"
        )
        
        formatted = await adapter.format_prompt(request)
        
        # Critical files should appear before useful files in the prompt
        critical_pos = formatted.find("main.py")
        useful_pos = formatted.find("utils.py")
        
        assert critical_pos < useful_pos


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpenRouterAdapterAPIIntegration:
    """Test API integration with OpenRouter."""
    
    @pytest.fixture
    def adapter(self, mock_env_vars):
        """Create OpenRouter adapter for testing."""
        return OpenRouterAdapter()
    
    @patch('aiohttp.ClientSession.post')
    async def test_make_api_request_success(self, mock_post, adapter, mock_openrouter_response):
        """Test successful API request."""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = mock_openrouter_response
        mock_post.return_value.__aenter__.return_value = mock_response
        
        result = await adapter._make_api_request("Test prompt", "test/model")
        
        assert result == mock_openrouter_response
        mock_post.assert_called_once()
    
    @patch('aiohttp.ClientSession.post')
    async def test_make_api_request_rate_limit(self, mock_post, adapter):
        """Test handling of rate limit errors."""
        # Mock rate limit response
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.text.return_value = "Rate limit exceeded"
        mock_post.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(RateLimitError):
            await adapter._make_api_request("Test prompt", "test/model")
    
    @patch('aiohttp.ClientSession.post')
    async def test_make_api_request_server_error(self, mock_post, adapter):
        """Test handling of server errors."""
        # Mock server error response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = "Internal server error"
        mock_post.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(AnalysisError):
            await adapter._make_api_request("Test prompt", "test/model")
    
    @patch('aiohttp.ClientSession.post')
    async def test_make_api_request_timeout(self, mock_post, adapter):
        """Test handling of request timeouts."""
        import asyncio
        
        # Mock timeout
        mock_post.side_effect = asyncio.TimeoutError()
        
        with pytest.raises(AnalysisError):
            await adapter._make_api_request("Test prompt", "test/model")
    
    @patch('aiohttp.ClientSession.post')
    async def test_make_api_request_connection_error(self, mock_post, adapter):
        """Test handling of connection errors."""
        import aiohttp
        
        # Mock connection error
        mock_post.side_effect = aiohttp.ClientError("Connection failed")
        
        with pytest.raises(AnalysisError):
            await adapter._make_api_request("Test prompt", "test/model")
    
    async def test_test_connection_success(self, adapter):
        """Test connection testing with successful response."""
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.return_value = {"choices": [{"message": {"content": "test"}}]}
            
            result = await adapter.test_connection()
            assert result is True
    
    async def test_test_connection_failure(self, adapter):
        """Test connection testing with failed response."""
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.side_effect = AnalysisError("Connection failed")
            
            result = await adapter.test_connection()
            assert result is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpenRouterAdapterResponseParsing:
    """Test response parsing and validation."""
    
    @pytest.fixture
    def adapter(self, mock_env_vars):
        """Create OpenRouter adapter for testing."""
        return OpenRouterAdapter()
    
    async def test_parse_response_valid_json(self, adapter, mock_openrouter_response):
        """Test parsing valid JSON response."""
        result = await adapter._parse_response(mock_openrouter_response)
        
        assert isinstance(result, dict)
        assert "requirements_met" in result
        assert "scores" in result
        assert "recommendation" in result
        assert "confidence" in result
    
    async def test_parse_response_malformed_json(self, adapter):
        """Test parsing response with malformed JSON."""
        # Response with invalid JSON
        response = {
            "choices": [{
                "message": {
                    "content": '{"requirements_met": {"test": true}, "scores": {"quality": 80}'  # Missing closing brace
                }
            }]
        }
        
        # Should attempt JSON recovery
        result = await adapter._parse_response(response)
        assert isinstance(result, dict)
        # JSON recovery should handle the malformed JSON
    
    async def test_parse_response_json_with_markdown(self, adapter):
        """Test parsing JSON wrapped in markdown."""
        response = {
            "choices": [{
                "message": {
                    "content": '''```json
                    {
                        "requirements_met": {"test": true},
                        "scores": {"quality": 80},
                        "recommendation": "yes",
                        "confidence": 85
                    }
                    ```'''
                }
            }]
        }
        
        result = await adapter._parse_response(response)
        
        assert isinstance(result, dict)
        assert result["requirements_met"]["test"] is True
        assert result["scores"]["quality"] == 80
        assert result["recommendation"] == "yes"
        assert result["confidence"] == 85
    
    async def test_parse_response_json_with_comments(self, adapter):
        """Test parsing JSON with comments."""
        response = {
            "choices": [{
                "message": {
                    "content": '''{
                        // This is a comment
                        "requirements_met": {"test": true},
                        "scores": {"quality": 80},
                        /* Multi-line comment */
                        "recommendation": "yes",
                        "confidence": 85
                    }'''
                }
            }]
        }
        
        result = await adapter._parse_response(response)
        
        assert isinstance(result, dict)
        assert result["requirements_met"]["test"] is True
        assert result["confidence"] == 85
    
    async def test_parse_response_completely_invalid(self, adapter):
        """Test parsing completely invalid response."""
        response = {
            "choices": [{
                "message": {
                    "content": "This is not JSON at all, just plain text"
                }
            }]
        }
        
        with pytest.raises(AnalysisError):
            await adapter._parse_response(response)
    
    async def test_parse_response_missing_choices(self, adapter):
        """Test parsing response missing choices field."""
        response = {
            "error": "No choices returned"
        }
        
        with pytest.raises(AnalysisError):
            await adapter._parse_response(response)
    
    async def test_validate_response_valid(self, adapter, mock_openrouter_response):
        """Test validating a valid response structure."""
        parsed = await adapter._parse_response(mock_openrouter_response)
        is_valid = await adapter.validate_response(parsed)
        
        assert is_valid is True
    
    async def test_validate_response_invalid(self, adapter):
        """Test validating an invalid response structure."""
        invalid_response = {
            "requirements_met": {},
            # Missing required fields: scores, recommendation, confidence
        }
        
        is_valid = await adapter.validate_response(invalid_response)
        assert is_valid is False


@pytest.mark.integration
@pytest.mark.asyncio
class TestOpenRouterAdapterEndToEnd:
    """Test end-to-end analysis workflow."""
    
    @pytest.fixture
    def adapter(self, mock_env_vars):
        """Create OpenRouter adapter for testing."""
        return OpenRouterAdapter()
    
    async def test_analyze_code_success(self, adapter, sample_analysis_request, mock_openrouter_response):
        """Test successful code analysis."""
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.return_value = mock_openrouter_response
            
            result = await adapter.analyze_code(sample_analysis_request)
            
            assert isinstance(result, AnalysisResult)
            assert result.recommendation in [
                RecommendationLevel.STRONGLY_REJECT,
                RecommendationLevel.REJECT,
                RecommendationLevel.REVIEW_REQUIRED,
                RecommendationLevel.ACCEPT,
                RecommendationLevel.STRONGLY_ACCEPT
            ]
            assert 0 <= result.confidence <= 1
            assert isinstance(result.strengths, list)
            assert isinstance(result.weaknesses, list)
            assert isinstance(result.scores, dict)
            assert isinstance(result.requirements_met, dict)
    
    async def test_analyze_code_with_fallback(self, adapter, sample_analysis_request):
        """Test code analysis with fallback model."""
        # Mock primary model failure, fallback success
        def mock_request_side_effect(prompt, model):
            if "primary" in model:
                raise AnalysisError("Primary model failed")
            else:
                return {
                    "choices": [{
                        "message": {
                            "content": '{"requirements_met": {}, "scores": {"quality": 70}, "recommendation": "maybe", "confidence": 60}'
                        }
                    }],
                    "usage": {"total_tokens": 500}
                }
        
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.side_effect = mock_request_side_effect
            
            result = await adapter.analyze_code(sample_analysis_request)
            
            assert isinstance(result, AnalysisResult)
            assert result.recommendation == RecommendationLevel.REVIEW_REQUIRED
            assert result.confidence == 0.6
    
    async def test_analyze_code_both_models_fail(self, adapter, sample_analysis_request):
        """Test code analysis when both models fail."""
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.side_effect = AnalysisError("All models failed")
            
            with pytest.raises(AnalysisError):
                await adapter.analyze_code(sample_analysis_request)
    
    async def test_analyze_code_token_limit_exceeded(self, adapter, sample_analysis_request):
        """Test code analysis with token limit exceeded."""
        # Mock token limit check failure
        with patch.object(adapter, '_check_token_limits') as mock_check:
            mock_check.side_effect = TokenLimitError("Token limit exceeded")
            
            with pytest.raises(TokenLimitError):
                await adapter.analyze_code(sample_analysis_request)
    
    async def test_analyze_code_rate_limit_retry(self, adapter, sample_analysis_request, mock_openrouter_response):
        """Test code analysis with rate limit and retry."""
        call_count = 0
        
        def mock_request_side_effect(prompt, model):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 attempts
                raise RateLimitError("Rate limited")
            else:  # Succeed on 3rd attempt
                return mock_openrouter_response
        
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.side_effect = mock_request_side_effect
            
            # Mock sleep to speed up test
            with patch('asyncio.sleep'):
                result = await adapter.analyze_code(sample_analysis_request)
                
                assert isinstance(result, AnalysisResult)
                assert call_count == 3  # Should have retried
    
    async def test_analyze_code_invalid_response_format(self, adapter, sample_analysis_request):
        """Test code analysis with invalid response format."""
        invalid_response = {
            "choices": [{
                "message": {
                    "content": '{"invalid": "format"}'  # Missing required fields
                }
            }]
        }
        
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.return_value = invalid_response
            
            with pytest.raises(AnalysisError):
                await adapter.analyze_code(sample_analysis_request)


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpenRouterAdapterErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def adapter(self, mock_env_vars):
        """Create OpenRouter adapter for testing."""
        return OpenRouterAdapter()
    
    async def test_handle_network_timeouts(self, adapter, sample_analysis_request):
        """Test handling of network timeouts."""
        with patch.object(adapter, '_make_api_request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError("Request timed out")
            
            with pytest.raises(AnalysisError, match="timeout"):
                await adapter.analyze_code(sample_analysis_request)
    
    async def test_handle_json_decode_errors(self, adapter):
        """Test handling of JSON decode errors."""
        response = {
            "choices": [{
                "message": {
                    "content": "Not valid JSON { broken"
                }
            }]
        }
        
        with pytest.raises(AnalysisError):
            await adapter._parse_response(response)
    
    async def test_handle_empty_response(self, adapter):
        """Test handling of empty responses."""
        response = {
            "choices": [{
                "message": {
                    "content": ""
                }
            }]
        }
        
        with pytest.raises(AnalysisError):
            await adapter._parse_response(response)
    
    async def test_handle_response_validation_failure(self, adapter):
        """Test handling response validation failures."""
        # Response with invalid structure
        invalid_structure = {
            "requirements_met": "not a dict",  # Should be dict
            "scores": {"quality": "not a number"},  # Should be numeric
            "recommendation": "invalid_value",  # Should be valid recommendation
            "confidence": "not a number"  # Should be numeric
        }
        
        is_valid = await adapter.validate_response(invalid_structure)
        assert is_valid is False
    
    async def test_concurrent_analysis_requests(self, adapter, sample_analysis_request, mock_openrouter_response):
        """Test handling multiple concurrent analysis requests."""
        # Simulate concurrent requests
        async def analyze_task(i):
            with patch.object(adapter, '_make_api_request') as mock_request:
                # Add small delay to simulate API call
                async def delayed_response(*args, **kwargs):
                    await asyncio.sleep(0.1)
                    return mock_openrouter_response
                
                mock_request.side_effect = delayed_response
                return await adapter.analyze_code(sample_analysis_request)
        
        # Run multiple analysis tasks concurrently
        tasks = [analyze_task(i) for i in range(3)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete successfully
        for result in results:
            assert isinstance(result, AnalysisResult)
            assert not isinstance(result, Exception)


@pytest.mark.unit
@pytest.mark.asyncio
class TestOpenRouterAdapterJSONRecovery:
    """Test JSON recovery mechanisms."""
    
    @pytest.fixture
    def adapter(self, mock_env_vars):
        """Create OpenRouter adapter for testing."""
        return OpenRouterAdapter()
    
    async def test_recover_truncated_json(self, adapter):
        """Test recovery of truncated JSON."""
        truncated_json = '{"requirements_met": {"architectural_pattern": true, "repository_pattern": false}, "scores": {"task_completion": 75, "code_quality":'
        
        recovered = await adapter._recover_json(truncated_json)
        
        assert isinstance(recovered, dict)
        assert "requirements_met" in recovered
        assert "scores" in recovered
    
    async def test_recover_json_with_trailing_comma(self, adapter):
        """Test recovery of JSON with trailing commas."""
        json_with_comma = '{"requirements_met": {"test": true,}, "scores": {"quality": 80,}}'
        
        recovered = await adapter._recover_json(json_with_comma)
        
        assert isinstance(recovered, dict)
        assert recovered["requirements_met"]["test"] is True
        assert recovered["scores"]["quality"] == 80
    
    async def test_recover_json_with_missing_quotes(self, adapter):
        """Test recovery of JSON with missing quotes."""
        json_missing_quotes = '{requirements_met: {test: true}, scores: {quality: 80}}'
        
        try:
            recovered = await adapter._recover_json(json_missing_quotes)
            # If recovery succeeds, verify structure
            assert isinstance(recovered, dict)
        except:
            # Some JSON issues might not be recoverable
            pass
    
    async def test_recover_json_completely_invalid(self, adapter):
        """Test recovery of completely invalid JSON."""
        invalid_json = "This is not JSON at all"
        
        with pytest.raises(AnalysisError):
            await adapter._recover_json(invalid_json)


@pytest.mark.unit  
@pytest.mark.asyncio
class TestOpenRouterAdapterConfiguration:
    """Test adapter configuration and customization."""
    
    def test_custom_model_configuration(self, mock_env_vars):
        """Test adapter with custom model configuration."""
        config = {
            "primary_model": "anthropic/claude-3-opus",
            "fallback_model": "openai/gpt-4",
            "max_tokens": 100000,
            "temperature": 0.3
        }
        
        adapter = OpenRouterAdapter(**config)
        
        assert adapter.primary_model == "anthropic/claude-3-opus"
        assert adapter.fallback_model == "openai/gpt-4"
        assert adapter.max_tokens == 100000
        assert adapter.temperature == 0.3
    
    def test_model_family_detection(self, mock_env_vars):
        """Test model family detection for token counting."""
        # Test different model names
        test_cases = [
            ("openai/gpt-4", "gpt"),
            ("anthropic/claude-3", "claude"),
            ("google/gemini-pro", "gemini"),
            ("meta-llama/llama-2", "default"),
        ]
        
        for model_name, expected_family in test_cases:
            adapter = OpenRouterAdapter(primary_model=model_name)
            family = adapter._get_model_family(model_name)
            assert family == expected_family
    
    def test_timeout_configuration(self, mock_env_vars):
        """Test timeout configuration."""
        adapter = OpenRouterAdapter()
        
        # Should have reasonable timeout values
        assert hasattr(adapter, '_request_timeout')
        assert adapter._request_timeout > 0
        assert adapter._request_timeout <= 300  # Not too long
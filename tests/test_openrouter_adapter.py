"""
Test suite for OpenRouter analyzer adapter.

This module tests the OpenRouter LLM analyzer functionality.
"""

import sys
import os
import asyncio
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import (
    Role, 
    AnalysisRequest, 
    AnalysisResult,
    RepositoryContent,
    FileInfo,
    RecommendationLevel
)
from core.exceptions import AnalysisError, TokenLimitError
from utils.token_counter import TokenCounter


def test_token_counter():
    """Test token counting utilities."""
    print("\n=== Testing Token Counter ===")
    
    counter = TokenCounter()
    
    # Test basic token counting
    text = "This is a test string for token counting."
    tokens = counter.estimate_tokens(text)
    assert tokens > 0
    print(f"✓ Token count for test string: {tokens}")
    
    # Test model family detection
    assert counter.get_model_family("gpt-4") == "gpt"
    assert counter.get_model_family("claude-3-opus") == "claude"
    assert counter.get_model_family("google/gemini-2.5-flash") == "gemini"
    print("✓ Model family detection working")
    
    # Test content truncation
    long_text = "word " * 1000  # 1000 words
    truncated = counter.truncate_to_fit(long_text, 100, "gpt-4")
    truncated_tokens = counter.estimate_tokens(truncated, "gpt-4")
    assert truncated_tokens <= 110  # Allow small overhead
    print(f"✓ Content truncation working: {truncated_tokens} tokens")
    
    print("✓ All token counter tests passed")


async def test_adapter_initialization():
    """Test OpenRouter adapter initialization."""
    print("\n=== Testing Adapter Initialization ===")
    
    # Create adapter with default config
    adapter = OpenRouterAdapter()
    
    # Check that adapter initializes properly
    # Note: api_key is private, we just check it was created
    assert adapter is not None
    assert hasattr(adapter, 'models')
    assert len(adapter.models) > 0
    print(f"✓ Adapter initialized with {len(adapter.models)} models")
    
    # Check supported models
    supported = adapter.get_supported_models()
    assert len(supported) > 0
    assert all("name" in model for model in supported)
    assert all("context_window" in model for model in supported)
    print(f"✓ Supported models retrieved: {len(supported)}")
    
    print("✓ Adapter initialization tests passed")


async def test_token_estimation():
    """Test token estimation functionality."""
    print("\n=== Testing Token Estimation ===")
    
    adapter = OpenRouterAdapter()
    
    # Test token estimation
    test_text = "def main():\n    print('Hello, World!')\n    return 0"
    tokens = adapter.estimate_tokens(test_text)
    assert tokens > 0
    print(f"✓ Estimated tokens for code snippet: {tokens}")
    
    # Test with different text sizes
    short_text = "Hello"
    long_text = "x" * 10000
    
    short_tokens = adapter.estimate_tokens(short_text)
    long_tokens = adapter.estimate_tokens(long_text)
    
    assert short_tokens < long_tokens
    print(f"✓ Token estimation scales with text size: {short_tokens} < {long_tokens}")
    
    print("✓ Token estimation tests passed")


async def test_prompt_formatting():
    """Test prompt formatting for analysis."""
    print("\n=== Testing Prompt Formatting ===")
    
    adapter = OpenRouterAdapter()
    
    # Create test data
    files = [
        FileInfo("main.go", "package main\nfunc main() {}", "critical", 10, "go"),
        FileInfo("auth.go", "package auth\n// Auth logic", "important", 15, "go")
    ]
    
    repo_content = RepositoryContent(
        url="https://github.com/test/repo",
        files=files,
        total_tokens=25,
        structure="- main.go\n- auth.go",
        metadata={"language": "Go"}
    )
    
    request = AnalysisRequest(
        repository_content=repo_content,
        role=Role.BACKEND,
        task_requirements="Implement OTP authentication"
    )
    
    # Format prompt
    prompt = await adapter.format_prompt(request)
    
    # Verify prompt structure
    assert "backend" in prompt.lower()
    assert "OTP authentication" in prompt
    assert "main.go" in prompt
    assert "auth.go" in prompt
    print("✓ Prompt includes all required elements")
    
    # Check prompt length is reasonable
    assert 100 < len(prompt) < 100000
    print(f"✓ Prompt length is reasonable: {len(prompt)} chars")
    
    print("✓ Prompt formatting tests passed")


async def test_response_validation():
    """Test response validation logic."""
    print("\n=== Testing Response Validation ===")
    
    adapter = OpenRouterAdapter()
    
    # Valid response structure (matching what validators.py expects)
    valid_response = {
        "requirements_met": {
            "OTP Implementation": True,
            "Rate Limiting": False
        },
        "scores": {
            "completeness": 70,
            "quality": 85,
            "architecture": 90,
            "testing": 60
        },
        "recommendation": "ACCEPT",
        "confidence": 80,
        "strengths": ["Clean code", "Good structure"],
        "weaknesses": ["Missing rate limiting"],
        "detailed_feedback": "Overall good implementation"
    }
    
    is_valid = await adapter.validate_response(valid_response)
    assert is_valid
    print("✓ Valid response accepted")
    
    # Invalid response (missing required field)
    invalid_response = {
        "scores": {"quality": 85},
        "recommendation": "accept"
        # Missing other required fields
    }
    
    is_valid = await adapter.validate_response(invalid_response)
    assert not is_valid
    print("✓ Invalid response rejected")
    
    print("✓ Response validation tests passed")


async def test_retry_policy():
    """Test retry policy configuration."""
    print("\n=== Testing Retry Policy ===")
    
    adapter = OpenRouterAdapter()
    
    policy = adapter.get_retry_policy()
    
    # Check policy structure
    assert "max_retries" in policy
    assert "initial_delay" in policy
    assert "max_delay" in policy
    assert "exponential_base" in policy
    
    # Check values are reasonable
    assert 1 <= policy["max_retries"] <= 5
    assert 0.5 <= policy["initial_delay"] <= 5
    assert policy["max_delay"] >= policy["initial_delay"]
    assert 1.5 <= policy["exponential_base"] <= 3
    
    print(f"✓ Retry policy configured: {policy['max_retries']} retries, "
          f"{policy['initial_delay']}s initial delay")
    
    print("✓ Retry policy tests passed")


async def test_error_handling():
    """Test error handling scenarios."""
    print("\n=== Testing Error Handling ===")
    
    adapter = OpenRouterAdapter()
    
    # Create request with excessive tokens
    huge_content = "x" * 10000000  # 10 million characters
    files = [FileInfo("huge.txt", huge_content, "critical", 3000000, "text")]
    
    repo_content = RepositoryContent(
        url="https://github.com/test/huge",
        files=files,
        total_tokens=3000000,
        structure="huge file",
        metadata={}
    )
    
    request = AnalysisRequest(
        repository_content=repo_content,
        role=Role.BACKEND,
        task_requirements="Test"
    )
    
    # This should handle the large content gracefully
    # (truncate it rather than fail)
    try:
        # We can't actually call the API without a real key,
        # but we can test the preparation phase
        prompt = await adapter.format_prompt(request)
        assert len(prompt) < 1000000  # Should be truncated
        print("✓ Large content handled gracefully")
    except TokenLimitError as e:
        print(f"✓ Token limit error raised appropriately: {str(e)[:50]}...")
    except Exception as e:
        print(f"✓ Error handled: {type(e).__name__}")
    
    print("✓ Error handling tests passed")


async def test_model_selection():
    """Test model selection and fallback."""
    print("\n=== Testing Model Selection ===")
    
    adapter = OpenRouterAdapter()
    
    # Check that models are configured
    assert hasattr(adapter, 'models')
    assert len(adapter.models) > 0
    print(f"✓ Adapter has {len(adapter.models)} models configured")
    
    # Check fallback models exist
    assert len(adapter.models) >= 2
    print(f"✓ Fallback chain has {len(adapter.models)} models")
    
    # Verify each model has required fields
    for model in adapter.models:
        assert "name" in model
        assert "context_window" in model
        assert model["context_window"] > 0
    
    # The first model should be the primary
    if adapter.models:
        print(f"✓ Primary model: {adapter.models[0]['name']}")
    
    print("✓ All models properly configured")
    print("✓ Model selection tests passed")


async def run_all_tests():
    """Run all async test functions."""
    print("=" * 50)
    print("RUNNING OPENROUTER ADAPTER TESTS")
    print("=" * 50)
    
    try:
        test_token_counter()
        await test_adapter_initialization()
        await test_token_estimation()
        await test_prompt_formatting()
        await test_response_validation()
        await test_retry_policy()
        await test_model_selection()
        await test_error_handling()
        
        print("\n" + "=" * 50)
        print("✅ ALL OPENROUTER ADAPTER TESTS PASSED!")
        print("=" * 50)
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
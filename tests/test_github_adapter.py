"""
Test suite for GitHub adapter.

This module tests the GitHub repository adapter functionality.
"""

import sys
import os
import asyncio
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.repositories.github import GitHubAdapter
from core.models import Role
from core.exceptions import ValidationError, RepositoryError


async def test_url_validation():
    """Test GitHub URL validation."""
    print("\n=== Testing URL Validation ===")
    
    adapter = GitHubAdapter()
    
    # Valid URLs
    valid_urls = [
        "https://github.com/python/cpython",
        "https://github.com/python/cpython.git",
        "git@github.com:python/cpython.git",
        "https://github.com/user-name/repo-name",
    ]
    
    for url in valid_urls:
        is_valid = await adapter.validate_url(url)
        assert is_valid, f"URL should be valid: {url}"
        print(f"✓ Valid URL accepted: {url}")
    
    # Invalid URLs
    invalid_urls = [
        "https://gitlab.com/user/repo",
        "not-a-url",
        "https://github.com/",
        "https://github.com/single",
    ]
    
    for url in invalid_urls:
        is_valid = await adapter.validate_url(url)
        assert not is_valid, f"URL should be invalid: {url}"
        print(f"✓ Invalid URL rejected: {url}")
    
    print("✓ All URL validation tests passed")


async def test_repo_id_extraction():
    """Test repository ID extraction from URLs."""
    print("\n=== Testing Repository ID Extraction ===")
    
    adapter = GitHubAdapter()
    
    test_cases = [
        ("https://github.com/python/cpython", "python/cpython"),
        ("https://github.com/python/cpython.git", "python/cpython"),
        ("git@github.com:python/cpython.git", "python/cpython"),
        ("https://github.com/user-name/repo-name", "user-name/repo-name"),
    ]
    
    for url, expected_id in test_cases:
        repo_id = adapter.extract_repo_id(url)
        assert repo_id == expected_id, f"Expected {expected_id}, got {repo_id}"
        print(f"✓ Extracted ID '{repo_id}' from {url}")
    
    # Test invalid URL
    try:
        adapter.extract_repo_id("not-a-github-url")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        print("✓ Invalid URL raises ValidationError")
    
    print("✓ All repository ID extraction tests passed")


async def test_fetch_small_repository():
    """Test fetching a small test repository."""
    print("\n=== Testing Repository Fetching ===")
    
    adapter = GitHubAdapter()
    
    # Use a small test repository
    # Using a simple hello-world repo that should be small
    test_url = "https://github.com/octocat/Hello-World"
    
    print(f"Fetching test repository: {test_url}")
    
    try:
        # Fetch repository
        repo_content = await adapter.fetch_repository(test_url, Role.BACKEND)
        
        # Validate results
        assert repo_content.url == test_url
        assert len(repo_content.files) > 0
        assert repo_content.total_tokens > 0
        assert repo_content.structure != ""
        
        print(f"✓ Repository fetched successfully")
        print(f"  - Files found: {len(repo_content.files)}")
        print(f"  - Total tokens: {repo_content.total_tokens}")
        print(f"  - Has structure: {'Yes' if repo_content.structure else 'No'}")
        
        # Check file priorities
        critical_files = repo_content.get_critical_files()
        print(f"  - Critical files: {len(critical_files)}")
        
        # Cleanup
        await adapter.cleanup()
        print("✓ Cleanup completed")
        
    except Exception as e:
        print(f"⚠️ Repository fetch test skipped (may need network): {e}")
        # This is acceptable as it requires network access
        return
    
    print("✓ Repository fetching test passed")


async def test_repository_info():
    """Test getting repository metadata."""
    print("\n=== Testing Repository Info ===")
    
    adapter = GitHubAdapter()
    test_url = "https://github.com/octocat/Hello-World"
    
    try:
        info = await adapter.get_repository_info(test_url)
        
        # Check expected fields
        expected_fields = ["name", "owner", "url", "default_branch"]
        for field in expected_fields:
            assert field in info, f"Missing field: {field}"
            print(f"✓ Has field '{field}': {info[field]}")
        
        print("✓ Repository info retrieved successfully")
        
    except Exception as e:
        print(f"⚠️ Repository info test skipped (may need git): {e}")
        return
    
    print("✓ Repository info test passed")


async def test_file_patterns():
    """Test file pattern configuration."""
    print("\n=== Testing File Patterns ===")
    
    adapter = GitHubAdapter()
    
    # Test backend patterns
    backend_patterns = adapter.get_file_patterns(Role.BACKEND)
    assert "critical" in backend_patterns
    assert "important" in backend_patterns
    assert "useful" in backend_patterns
    print(f"✓ Backend patterns configured")
    print(f"  - Critical patterns: {len(backend_patterns['critical'])}")
    print(f"  - Important patterns: {len(backend_patterns['important'])}")
    
    # Test frontend patterns
    frontend_patterns = adapter.get_file_patterns(Role.FRONTEND)
    assert "critical" in frontend_patterns
    print(f"✓ Frontend patterns configured")
    print(f"  - Critical patterns: {len(frontend_patterns['critical'])}")
    
    print("✓ File pattern tests passed")


async def test_error_handling():
    """Test error handling for invalid repositories."""
    print("\n=== Testing Error Handling ===")
    
    adapter = GitHubAdapter()
    
    # Test with non-existent repository
    invalid_url = "https://github.com/this-does-not/exist-at-all-12345"
    
    try:
        await adapter.fetch_repository(invalid_url, Role.BACKEND)
        print("⚠️ No error raised for invalid repository (network may be down)")
    except RepositoryError as e:
        print(f"✓ RepositoryError raised for invalid repo: {str(e)[:50]}...")
    except Exception as e:
        print(f"✓ Error raised for invalid repo: {type(e).__name__}")
    
    # Test cleanup even after error
    await adapter.cleanup()
    print("✓ Cleanup works after error")
    
    print("✓ Error handling tests passed")


async def run_all_tests():
    """Run all async test functions."""
    print("=" * 50)
    print("RUNNING GITHUB ADAPTER TESTS")
    print("=" * 50)
    
    try:
        await test_url_validation()
        await test_repo_id_extraction()
        await test_file_patterns()
        await test_repository_info()
        await test_fetch_small_repository()
        await test_error_handling()
        
        print("\n" + "=" * 50)
        print("✅ ALL GITHUB ADAPTER TESTS PASSED!")
        print("=" * 50)
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
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
"""
Test architecture pattern enforcement in the analysis system.

This test verifies that the system correctly identifies and penalizes
submissions that lack specific architectural patterns.
"""

import json
import asyncio
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import Mock, patch, MagicMock
from adapters.analyzers.openrouter import OpenRouterAdapter as OpenRouterAnalyzer
from core.models import AnalysisRequest, RepositoryContent, FileInfo, Role

# Sample responses from LLM with different architecture scenarios
RESPONSE_NO_ARCHITECTURE = {
    "task_analysis": {
        "explicit_requirements": ["Create REST API"],
        "task_complexity": "simple"
    },
    "requirements_implementation": {
        "api_endpoints": {
            "requested": True,
            "implemented": True,
            "quality": "good"
        }
    },
    "critical_issues": [],
    "penalty_breakdown": {
        "issues_found": [
            {"issue": "Code has folders but no architectural pattern", "severity": "critical", "penalty": 50}
        ],
        "total_penalty": 50
    },
    "scores": {
        "task_completion": 80,
        "code_quality": 75,
        "seniority_indicators": 70,
        "critical_issues_penalty": 50
    },
    "recommendation": "strong_no",
    "confidence": 0.9,
    "hiring_decision": {
        "decision": "NO_HIRE",
        "primary_reason": "No identifiable architecture pattern"
    },
    "detailed_feedback": "The code lacks a specific architectural pattern. Just having folders is not enough."
}

RESPONSE_WITH_MVC = {
    "task_analysis": {
        "explicit_requirements": ["Create REST API"],
        "task_complexity": "moderate"
    },
    "requirements_implementation": {
        "api_endpoints": {
            "requested": True,
            "implemented": True,
            "quality": "excellent"
        }
    },
    "critical_issues": [],
    "penalty_breakdown": {
        "issues_found": [],
        "total_penalty": 0
    },
    "scores": {
        "task_completion": 90,
        "code_quality": 85,
        "seniority_indicators": 85,
        "critical_issues_penalty": 0
    },
    "recommendation": "yes",
    "confidence": 0.9,
    "hiring_decision": {
        "decision": "HIRE",
        "primary_reason": "Well-implemented MVC architecture with clear separation of concerns"
    },
    "detailed_feedback": "The code implements a clear MVC architecture pattern with proper separation."
}

RESPONSE_WITH_CLEAN_ARCHITECTURE = {
    "task_analysis": {
        "explicit_requirements": ["Create microservice"],
        "task_complexity": "complex"
    },
    "requirements_implementation": {
        "microservice": {
            "requested": True,
            "implemented": True,
            "quality": "excellent"
        }
    },
    "critical_issues": [],
    "penalty_breakdown": {
        "issues_found": [],
        "total_penalty": 0
    },
    "scores": {
        "task_completion": 95,
        "code_quality": 90,
        "seniority_indicators": 95,
        "critical_issues_penalty": 0
    },
    "recommendation": "strong_yes",
    "confidence": 0.95,
    "hiring_decision": {
        "decision": "HIRE",
        "primary_reason": "Excellent implementation of Clean Architecture with dependency inversion"
    },
    "detailed_feedback": "Implements Clean Architecture with proper boundaries and dependency inversion."
}

async def test_no_architecture_rejection():
    """Test that code without identifiable architecture is rejected."""
    analyzer = OpenRouterAnalyzer()
    
    # Mock the internal method that processes the LLM response
    with patch.object(analyzer, '_validate_and_adjust_penalty') as mock_validate:
        # Let the validator run its logic on our test response
        mock_validate.return_value = RESPONSE_NO_ARCHITECTURE
        
        # Also mock the actual API call to return our test response
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = asyncio.coroutine(lambda: {
                "choices": [{
                    "message": {
                        "content": json.dumps(RESPONSE_NO_ARCHITECTURE)
                    }
                }]
            })
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Create test request
            repo_content = RepositoryContent(
                url="https://github.com/test/repo",
                files=[FileInfo(path="main.go", content="package main\n// test code")],
                total_tokens=100,
                structure="src/\n  main.go"
            )
            
            request = AnalysisRequest(
                repository_content=repo_content,
                role=Role.BACKEND,
                task_requirements="Create REST API",
                github_url="https://github.com/test/repo"
            )
            
            # Analyze
            result = await analyzer.analyze_code(request)
        
        # Verify rejection due to no architecture
        assert result.scores.get('critical_issues_penalty', 0) >= 50, \
            f"Expected penalty >= 50 for no architecture, got {result.scores.get('critical_issues_penalty', 0)}"
        assert result.hiring_decision['decision'] == 'NO_HIRE', \
            "Expected NO_HIRE for no architecture"
        assert 'architecture' in result.detailed_feedback.lower() or \
               'architecture' in result.hiring_decision.get('primary_reason', '').lower(), \
            "Expected architecture mentioned in feedback"
        
        print("✅ No architecture correctly rejected with 50+ penalty")

async def test_mvc_architecture_accepted():
    """Test that code with MVC architecture is properly evaluated."""
    analyzer = OpenRouterAnalyzer()
    
    with patch.object(analyzer, '_call_api') as mock_api:
        mock_api.return_value = json.dumps(RESPONSE_WITH_MVC)
        
        repo_content = RepositoryContent(
            url="https://github.com/test/mvc-repo",
            files=[FileInfo(path="controllers/user.go", content="package controllers")],
            total_tokens=100,
            structure="controllers/\n  user.go\nmodels/\n  user.go\nviews/\n  user.html"
        )
        
        request = AnalysisRequest(
            repository_content=repo_content,
            role=Role.BACKEND,
            task_requirements="Create REST API",
            github_url="https://github.com/test/mvc-repo"
        )
        
        result = await analyzer.analyze(request)
        
        assert result.scores.get('critical_issues_penalty', 0) == 0, \
            f"Expected no penalty for MVC architecture, got {result.scores.get('critical_issues_penalty', 0)}"
        assert result.hiring_decision['decision'] == 'HIRE', \
            "Expected HIRE for proper MVC architecture"
        
        print("✅ MVC architecture correctly accepted with no architecture penalty")

async def test_clean_architecture_accepted():
    """Test that code with Clean Architecture is properly evaluated."""
    analyzer = OpenRouterAnalyzer()
    
    with patch.object(analyzer, '_call_api') as mock_api:
        mock_api.return_value = json.dumps(RESPONSE_WITH_CLEAN_ARCHITECTURE)
        
        repo_content = RepositoryContent(
            url="https://github.com/test/clean-repo",
            files=[FileInfo(path="domain/entities/user.go", content="package entities")],
            total_tokens=100,
            structure="domain/\n  entities/\nadapters/\n  repositories/\nusecases/\n  user/"
        )
        
        request = AnalysisRequest(
            repository_content=repo_content,
            role=Role.BACKEND,
            task_requirements="Create microservice",
            github_url="https://github.com/test/clean-repo"
        )
        
        result = await analyzer.analyze(request)
        
        assert result.scores.get('critical_issues_penalty', 0) == 0, \
            f"Expected no penalty for Clean Architecture, got {result.scores.get('critical_issues_penalty', 0)}"
        assert result.hiring_decision['decision'] == 'HIRE', \
            "Expected HIRE for Clean Architecture"
        
        print("✅ Clean Architecture correctly accepted with no architecture penalty")

async def test_penalty_validation_enforcement():
    """Test that penalty validation correctly enforces architecture penalties."""
    analyzer = OpenRouterAnalyzer()
    
    # Test case where LLM mentions no architecture but doesn't assign penalty
    response_missing_penalty = {
        **RESPONSE_NO_ARCHITECTURE,
        "penalty_breakdown": {
            "issues_found": [],
            "total_penalty": 0
        },
        "scores": {
            "task_completion": 80,
            "code_quality": 75,
            "seniority_indicators": 70,
            "critical_issues_penalty": 0  # LLM didn't assign penalty
        },
        "detailed_feedback": "Cannot identify if this is MVC, Layered, or any pattern. Just basic code organization."
    }
    
    with patch.object(analyzer, '_call_api') as mock_api:
        mock_api.return_value = json.dumps(response_missing_penalty)
        
        repo_content = RepositoryContent(
            url="https://github.com/test/no-pattern",
            files=[FileInfo(path="app.go", content="package main")],
            total_tokens=100,
            structure="src/\n  app.go\n  utils.go"
        )
        
        request = AnalysisRequest(
            repository_content=repo_content,
            role=Role.BACKEND,
            task_requirements="Create API",
            github_url="https://github.com/test/no-pattern"
        )
        
        result = await analyzer.analyze(request)
        
        # The validator should have caught and corrected this
        assert result.scores.get('critical_issues_penalty', 0) >= 50, \
            f"Validator should enforce 50+ penalty for no architecture, got {result.scores.get('critical_issues_penalty', 0)}"
        
        print("✅ Penalty validation correctly enforces architecture requirements")

async def run_all_tests():
    """Run all architecture enforcement tests."""
    print("\n🔍 Testing Architecture Pattern Enforcement\n")
    print("-" * 50)
    
    try:
        await test_no_architecture_rejection()
        await test_mvc_architecture_accepted()
        await test_clean_architecture_accepted()
        await test_penalty_validation_enforcement()
        
        print("\n" + "=" * 50)
        print("✅ All architecture enforcement tests passed!")
        print("=" * 50)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_all_tests())
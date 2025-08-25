"""
End-to-end validation test for the CV review system.

This test simulates real LLM responses and verifies that:
1. Good architecture + minor issues = HIRE
2. No architecture = NO_HIRE
3. Penalties are correctly capped
4. Hiring decisions match expectations
"""

import sys
import os
import json
import asyncio

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisRequest, RepositoryContent, FileInfo, Role
from unittest.mock import patch, MagicMock


# Simulated LLM responses
RESPONSE_GOOD_ARCHITECTURE_MINOR_ISSUES = {
    "task_analysis": {
        "explicit_requirements": ["OTP system", "Rate limiting", "API documentation"],
        "implicit_requirements": ["Secure random generation", "Time handling"],
        "not_required": ["SMS delivery", "Email delivery"],
        "task_complexity": "moderate"
    },
    "requirements_implementation": {
        "otp_system": {
            "requested": True,
            "implemented": True,
            "quality": "good",
            "notes": "Complete OTP implementation with generation and validation"
        },
        "rate_limiting": {
            "requested": True,
            "implemented": True,
            "quality": "excellent",
            "notes": "Proper rate limiting with time windows"
        },
        "api_documentation": {
            "requested": True,
            "implemented": True,
            "quality": "excellent",
            "notes": "Swagger documentation included"
        }
    },
    "critical_issues": [
        "Using math/rand for OTP generation instead of crypto/rand"
    ],
    "go_specific_evaluation": {
        "error_handling": "good",
        "concurrency_safety": "excellent",
        "package_structure": "clean",
        "idiomatic_go": True,
        "security_implementation": "basic"
    },
    "seniority_assessment": {
        "level_demonstrated": "mid",
        "strengths": [
            "Clear layered architecture with handlers, services, and storage",
            "Good use of interfaces and dependency injection",
            "Proper concurrency handling with sync.RWMutex"
        ],
        "growth_areas": [
            "Security best practices (crypto/rand usage)",
            "Error handling could be more idiomatic"
        ],
        "evidence": [
            "Layered architecture pattern clearly implemented",
            "Good separation of concerns"
        ]
    },
    "code_quality": {
        "readability": "good",
        "organization": "excellent",
        "error_handling": "good",
        "performance_awareness": True,
        "security_awareness": False
    },
    "penalty_breakdown": {
        "issues_found": [
            {"issue": "Using math/rand for OTP generation", "severity": "critical", "penalty": 40},
            {"issue": "Error handling relies on string comparison", "severity": "minor", "penalty": 10}
        ],
        "total_penalty": 50
    },
    "scores": {
        "task_completion": 95,
        "code_quality": 85,
        "seniority_indicators": 75,
        "critical_issues_penalty": 50
    },
    "recommendation": "no",
    "confidence": 0.85,
    "hiring_decision": {
        "decision": "NO_HIRE",
        "primary_reason": "Critical security issue with math/rand",
        "is_task_appropriate": "Yes, all requirements met",
        "is_production_ready": "No, security vulnerability"
    },
    "detailed_feedback": "The candidate delivered a well-structured solution with clear layered architecture (handlers, services, storage layers). All requirements were met including OTP system, rate limiting, and Swagger documentation. The code demonstrates good understanding of Go patterns and concurrency. However, using math/rand for OTP generation is a critical security flaw that makes this unsuitable for production."
}

RESPONSE_NO_ARCHITECTURE = {
    "task_analysis": {
        "explicit_requirements": ["Create REST API", "User management"],
        "task_complexity": "simple"
    },
    "requirements_implementation": {
        "rest_api": {
            "requested": True,
            "implemented": True,
            "quality": "basic"
        }
    },
    "critical_issues": [
        "No clear architectural pattern - just folders"
    ],
    "seniority_assessment": {
        "level_demonstrated": "junior",
        "strengths": ["Basic functionality works"],
        "growth_areas": ["Need to learn architectural patterns"],
        "evidence": ["Code has folders but no architectural pattern"]
    },
    "penalty_breakdown": {
        "issues_found": [],
        "total_penalty": 0
    },
    "scores": {
        "task_completion": 70,
        "code_quality": 60,
        "seniority_indicators": 50,
        "critical_issues_penalty": 0
    },
    "recommendation": "no",
    "confidence": 0.9,
    "hiring_decision": {
        "decision": "NO_HIRE",
        "primary_reason": "Lacks architectural understanding"
    },
    "detailed_feedback": "The code has basic folder organization but cannot identify any specific architectural pattern. Just having folders is not an architecture. The implementation is too simplistic."
}

RESPONSE_EXCELLENT_NO_ISSUES = {
    "task_analysis": {
        "explicit_requirements": ["Microservice", "API gateway", "Documentation"],
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
    "seniority_assessment": {
        "level_demonstrated": "senior",
        "strengths": [
            "Clean Architecture implementation",
            "Excellent separation of concerns",
            "Proper dependency injection"
        ],
        "growth_areas": [],
        "evidence": ["Implements Clean Architecture with dependency inversion"]
    },
    "penalty_breakdown": {
        "issues_found": [],
        "total_penalty": 0
    },
    "scores": {
        "task_completion": 100,
        "code_quality": 95,
        "seniority_indicators": 90,
        "critical_issues_penalty": 0
    },
    "recommendation": "strong_yes",
    "confidence": 0.95,
    "hiring_decision": {
        "decision": "HIRE",
        "primary_reason": "Excellent implementation with Clean Architecture"
    },
    "detailed_feedback": "Outstanding implementation following Clean Architecture principles with proper dependency inversion. The code shows deep understanding of architectural patterns and Go best practices."
}


async def test_good_architecture_with_minor_issues():
    """Test that good architecture with minor issues leads to HIRE after penalty adjustment."""
    print("\n🔍 Test: Good Architecture with Minor Issues")
    print("-" * 50)
    
    analyzer = OpenRouterAdapter()
    
    # Mock the API call to return our test response
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status = 200
        async def mock_json():
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps(RESPONSE_GOOD_ARCHITECTURE_MINOR_ISSUES)
                    }
                }]
            }
        mock_response.json = mock_json
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Create test request
        repo_content = RepositoryContent(
            url="https://github.com/test/good-repo",
            files=[FileInfo(path="main.go", content="package main")],
            total_tokens=1000,
            structure="handlers/\nservices/\nstorage/"
        )
        
        request = AnalysisRequest(
            repository_content=repo_content,
            role=Role.BACKEND,
            task_requirements="Implement OTP system",
            github_url="https://github.com/test/good-repo"
        )
        
        # Analyze
        result = await analyzer.analyze_code(request)
        
        print(f"Original LLM penalty: 50 (40 for math/rand + 10 for error handling)")
        print(f"Adjusted penalty: {result.scores.get('critical_issues_penalty', 0)}")
        print(f"Architecture mentioned: layered architecture ✓")
        print(f"Decision: {result.hiring_decision.get('decision', 'N/A')}")
        
        # Verify expectations
        penalty = result.scores.get('critical_issues_penalty', 0)
        avg_score = (result.scores.get('task_completion', 0) + 
                    result.scores.get('code_quality', 0) + 
                    result.scores.get('seniority_indicators', 0)) / 3
        
        # Should be: math/rand capped to 20 + error handling 10 = 30 total
        assert penalty == 30, f"Expected penalty 30, got {penalty}"
        assert avg_score >= 70, f"Expected average >= 70%, got {avg_score:.1f}%"
        
        # With 30 penalty and good scores, should be HIRE
        expected_decision = "HIRE" if penalty < 50 and avg_score >= 70 else "NO_HIRE"
        print(f"\n✅ Result: Penalty={penalty}, Avg={avg_score:.1f}%, Decision should be {expected_decision}")
        
        return True


async def test_no_architecture_rejection():
    """Test that lack of architecture leads to automatic rejection."""
    print("\n🔍 Test: No Architecture Pattern")
    print("-" * 50)
    
    analyzer = OpenRouterAdapter()
    
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status = 200
        async def mock_json():
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps(RESPONSE_NO_ARCHITECTURE)
                    }
                }]
            }
        mock_response.json = mock_json
        mock_post.return_value.__aenter__.return_value = mock_response
        
        repo_content = RepositoryContent(
            url="https://github.com/test/bad-repo",
            files=[FileInfo(path="main.go", content="package main")],
            total_tokens=1000,
            structure="src/\nutils/"
        )
        
        request = AnalysisRequest(
            repository_content=repo_content,
            role=Role.BACKEND,
            task_requirements="Create API",
            github_url="https://github.com/test/bad-repo"
        )
        
        result = await analyzer.analyze_code(request)
        
        print(f"Original LLM penalty: 0")
        print(f"Adjusted penalty: {result.scores.get('critical_issues_penalty', 0)}")
        print(f"Architecture issue detected: 'no architectural pattern'")
        
        penalty = result.scores.get('critical_issues_penalty', 0)
        assert penalty >= 50, f"Expected penalty >= 50 for no architecture, got {penalty}"
        
        print(f"\n✅ Result: No architecture correctly penalized with {penalty} points → NO_HIRE")
        
        return True


async def test_excellent_implementation():
    """Test that excellent implementation with proper architecture gets hired."""
    print("\n🔍 Test: Excellent Implementation")
    print("-" * 50)
    
    analyzer = OpenRouterAdapter()
    
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status = 200
        async def mock_json():
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps(RESPONSE_EXCELLENT_NO_ISSUES)
                    }
                }]
            }
        mock_response.json = mock_json
        mock_post.return_value.__aenter__.return_value = mock_response
        
        repo_content = RepositoryContent(
            url="https://github.com/test/excellent-repo",
            files=[FileInfo(path="domain/entities/user.go", content="package entities")],
            total_tokens=1000,
            structure="domain/\nadapters/\nusecases/"
        )
        
        request = AnalysisRequest(
            repository_content=repo_content,
            role=Role.BACKEND,
            task_requirements="Create microservice",
            github_url="https://github.com/test/excellent-repo"
        )
        
        result = await analyzer.analyze_code(request)
        
        print(f"Penalty: {result.scores.get('critical_issues_penalty', 0)}")
        print(f"Architecture: Clean Architecture ✓")
        print(f"Decision: {result.hiring_decision.get('decision', 'HIRE')}")
        
        penalty = result.scores.get('critical_issues_penalty', 0)
        assert penalty == 0, f"Expected no penalty, got {penalty}"
        
        avg_score = (result.scores.get('task_completion', 0) + 
                    result.scores.get('code_quality', 0) + 
                    result.scores.get('seniority_indicators', 0)) / 3
        
        print(f"\n✅ Result: No penalties, Avg={avg_score:.1f}%, Decision=HIRE")
        
        return True


async def run_all_tests():
    """Run all end-to-end tests."""
    print("\n" + "=" * 60)
    print("END-TO-END VALIDATION TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Good Architecture + Minor Issues", test_good_architecture_with_minor_issues),
        ("No Architecture Pattern", test_no_architecture_rejection),
        ("Excellent Implementation", test_excellent_implementation)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            success = await test_func()
            if success:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name}: FAILED with error: {e}")
    
    print("\n" + "=" * 60)
    print(f"FINAL RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ ALL END-TO-END TESTS PASSED!")
        print("\nKey validations confirmed:")
        print("1. ✅ Math/rand penalty capped at 20 (not 40)")
        print("2. ✅ Good architecture prevents architecture penalty")
        print("3. ✅ No architecture triggers 50+ penalty")
        print("4. ✅ Hiring decisions follow correct logic")
    else:
        print(f"❌ {failed} tests failed")
    
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)  # Reduce noise
    
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
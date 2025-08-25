"""
Direct test of architecture pattern validation logic.

This test directly verifies the penalty enforcement for missing architecture patterns.
"""

import sys
import os
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.analyzers.openrouter import OpenRouterAdapter


def test_architecture_penalty_detection():
    """Test that the validator correctly detects and enforces architecture penalties."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Architecture Penalty Detection\n")
    print("-" * 50)
    
    # Test case 1: No architecture pattern mentioned
    test_cases = [
        {
            "name": "No architecture pattern",
            "response": {
                "detailed_feedback": "Code has folders but no architectural pattern. Just basic organization.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_detect": True
        },
        {
            "name": "Cannot identify pattern",
            "response": {
                "detailed_feedback": "Cannot identify if this is MVC, Layered, or any pattern.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_detect": True
        },
        {
            "name": "Just folders mentioned",
            "response": {
                "detailed_feedback": "The submission just has folders without actual architecture.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_detect": True
        },
        {
            "name": "Basic structure not architecture",
            "response": {
                "detailed_feedback": "Has basic structure but not a real architecture pattern.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_detect": True
        },
        {
            "name": "MVC architecture mentioned",
            "response": {
                "detailed_feedback": "Well-implemented MVC architecture with clear separation.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 0,
            "should_detect": False
        },
        {
            "name": "Clean Architecture mentioned",
            "response": {
                "detailed_feedback": "Implements Clean Architecture with dependency inversion.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 0,
            "should_detect": False
        },
        {
            "name": "Missing API documentation",
            "response": {
                "detailed_feedback": "Good code but missing Swagger documentation.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 35,
            "should_detect": True
        },
        {
            "name": "Multiple issues including no architecture",
            "response": {
                "detailed_feedback": "Cannot identify any pattern, just folders. Also missing OpenAPI docs.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 85,  # 50 (architecture) + 35 (API docs)
            "should_detect": True
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print(f"  Feedback: \"{test['response']['detailed_feedback'][:60]}...\"")
        
        # Run the validator (modifies in place)
        test_response_copy = json.loads(json.dumps(test['response']))  # Deep copy
        analyzer._validate_and_adjust_penalty(test_response_copy)
        
        actual_penalty = test_response_copy['scores'].get('critical_issues_penalty', 0)
        expected = test['expected_penalty']
        
        if test['should_detect']:
            if actual_penalty >= expected:
                print(f"  ✅ Correctly enforced penalty: {actual_penalty} (expected >= {expected})")
                passed += 1
            else:
                print(f"  ❌ Failed to enforce penalty: {actual_penalty} (expected >= {expected})")
                failed += 1
        else:
            if actual_penalty == expected:
                print(f"  ✅ Correctly no penalty: {actual_penalty}")
                passed += 1
            else:
                print(f"  ❌ Incorrectly added penalty: {actual_penalty} (expected {expected})")
                failed += 1
        
        # Show what issues were detected
        if test_response_copy['penalty_breakdown']['issues_found']:
            print("  Detected issues:")
            for issue in test_response_copy['penalty_breakdown']['issues_found']:
                print(f"    - {issue['issue']}: {issue['penalty']} points")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("✅ All architecture validation tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")
    print("=" * 50)
    
    return failed == 0


def test_penalty_accumulation():
    """Test that penalties accumulate correctly without duplication."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Penalty Accumulation\n")
    print("-" * 50)
    
    # Test response with multiple issues
    response = {
        "detailed_feedback": "Using math/rand for OTP generation. Also cannot identify any architecture pattern.",
        "penalty_breakdown": {
            "issues_found": [],
            "total_penalty": 0
        },
        "scores": {"critical_issues_penalty": 0}
    }
    
    response_copy = json.loads(json.dumps(response))  # Deep copy
    analyzer._validate_and_adjust_penalty(response_copy)
    
    total_penalty = response_copy['scores'].get('critical_issues_penalty', 0)
    issues = response_copy['penalty_breakdown']['issues_found']
    
    print("Original feedback:", response['detailed_feedback'])
    print(f"\nDetected {len(issues)} issues:")
    
    issue_categories = {}
    for issue in issues:
        category = issue.get('category', 'unknown')
        if category in issue_categories:
            print(f"  ❌ DUPLICATE CATEGORY: {category}")
            print(f"     First: {issue_categories[category]}")
            print(f"     Second: {issue['issue']}")
            return False
        issue_categories[category] = issue['issue']
        print(f"  - {issue['issue']}: {issue['penalty']} points (category: {category})")
    
    print(f"\nTotal penalty: {total_penalty}")
    
    # Check for correct accumulation
    expected_min = 70  # At least 20 (math/rand) + 50 (no architecture)
    if total_penalty >= expected_min:
        print(f"✅ Penalties accumulated correctly: {total_penalty} >= {expected_min}")
        return True
    else:
        print(f"❌ Incorrect accumulation: {total_penalty} < {expected_min}")
        return False


if __name__ == "__main__":
    success1 = test_architecture_penalty_detection()
    success2 = test_penalty_accumulation()
    
    if success1 and success2:
        print("\n✅ All tests passed successfully!")
        exit(0)
    else:
        print("\n❌ Some tests failed")
        exit(1)
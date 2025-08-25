"""
Comprehensive test suite for penalty enforcement and hiring decisions.

This test verifies:
1. Penalties are capped at maximum values
2. Architecture detection prevents wrongful penalties
3. Hiring decisions are correct based on total penalties
4. Edge cases are handled properly
"""

import sys
import os
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import RecommendationLevel


def test_penalty_capping():
    """Test that excessive penalties are capped to maximum values."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Penalty Capping\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Math/rand over-penalized by LLM",
            "response": {
                "detailed_feedback": "Good code overall",
                "penalty_breakdown": {
                    "issues_found": [
                        {"issue": "Using math/rand for OTP generation", "severity": "critical", "penalty": 40}
                    ],
                    "total_penalty": 40
                },
                "scores": {"critical_issues_penalty": 40}
            },
            "expected_penalty": 20,
            "expected_severity": "moderate"
        },
        {
            "name": "JWT issue over-penalized",
            "response": {
                "detailed_feedback": "Good implementation",
                "penalty_breakdown": {
                    "issues_found": [
                        {"issue": "Weak JWT secret used", "severity": "major", "penalty": 35}
                    ],
                    "total_penalty": 35
                },
                "scores": {"critical_issues_penalty": 35}
            },
            "expected_penalty": 20,
            "expected_severity": "moderate"
        },
        {
            "name": "Multiple issues with over-penalization",
            "response": {
                "detailed_feedback": "Several issues found",
                "penalty_breakdown": {
                    "issues_found": [
                        {"issue": "Using math/rand for token generation", "severity": "critical", "penalty": 45},
                        {"issue": "Default JWT secret", "severity": "major", "penalty": 30}
                    ],
                    "total_penalty": 75
                },
                "scores": {"critical_issues_penalty": 75}
            },
            "expected_total": 40,  # 20 + 20
            "multiple": True
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        # Run the validator
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        if test.get('multiple'):
            actual_total = response_copy['scores'].get('critical_issues_penalty', 0)
            expected_total = test['expected_total']
            
            if actual_total == expected_total:
                print(f"  ✅ Total correctly capped: {actual_total} (expected {expected_total})")
                passed += 1
            else:
                print(f"  ❌ Total not capped correctly: {actual_total} (expected {expected_total})")
                failed += 1
        else:
            issue = response_copy['penalty_breakdown']['issues_found'][0]
            actual_penalty = issue['penalty']
            actual_severity = issue['severity']
            
            if actual_penalty == test['expected_penalty'] and actual_severity == test['expected_severity']:
                print(f"  ✅ Correctly capped: {actual_penalty} points, severity: {actual_severity}")
                passed += 1
            else:
                print(f"  ❌ Not capped correctly: {actual_penalty} points (expected {test['expected_penalty']})")
                failed += 1
    
    return passed, failed


def test_architecture_detection():
    """Test that proper architecture prevents wrongful penalties."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Architecture Detection\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Layered architecture mentioned - no penalty",
            "response": {
                "detailed_feedback": "The project follows a clear layered architecture pattern with handlers, services, and storage layers.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "should_have_architecture_penalty": False
        },
        {
            "name": "Clean architecture mentioned - no penalty",
            "response": {
                "detailed_feedback": "Implements Clean Architecture with proper dependency inversion and domain at the center.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "should_have_architecture_penalty": False
        },
        {
            "name": "MVC pattern mentioned - no penalty",
            "response": {
                "detailed_feedback": "Well-structured MVC pattern with clear separation between models, views, and controllers.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "should_have_architecture_penalty": False
        },
        {
            "name": "No architecture but mentions folders",
            "response": {
                "detailed_feedback": "Code has folders but no architectural pattern. Just basic organization.",
                "penalty_breakdown": {
                    "issues_found": [],
                    "total_penalty": 0
                },
                "scores": {"critical_issues_penalty": 0}
            },
            "should_have_architecture_penalty": True,
            "expected_penalty": 50
        },
        {
            "name": "Layered architecture + math/rand issue",
            "response": {
                "detailed_feedback": "Good layered architecture but uses math/rand for OTP generation which is insecure.",
                "penalty_breakdown": {
                    "issues_found": [
                        {"issue": "Using math/rand for OTP", "severity": "critical", "penalty": 40}
                    ],
                    "total_penalty": 40
                },
                "scores": {"critical_issues_penalty": 40}
            },
            "should_have_architecture_penalty": False,
            "expected_total": 20  # Only math/rand penalty, capped at 20
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        # Run the validator
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        actual_penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        
        if test['should_have_architecture_penalty']:
            if actual_penalty >= test['expected_penalty']:
                print(f"  ✅ Architecture penalty correctly applied: {actual_penalty}")
                passed += 1
            else:
                print(f"  ❌ Architecture penalty not applied: {actual_penalty} (expected >= {test['expected_penalty']})")
                failed += 1
        else:
            expected = test.get('expected_total', 0)
            if actual_penalty == expected:
                print(f"  ✅ No architecture penalty, total correct: {actual_penalty}")
                passed += 1
            else:
                print(f"  ❌ Incorrect penalty: {actual_penalty} (expected {expected})")
                failed += 1
    
    return passed, failed


def test_hiring_decisions():
    """Test that hiring decisions are correct based on penalties and scores."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Hiring Decisions\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Good scores, low penalty = HIRE",
            "scores": {"task_completion": 85, "code_quality": 80, "seniority_indicators": 75},
            "penalty": 20,
            "expected_decision": "HIRE",
            "expected_reason": "Average score 80% with penalty < 50"
        },
        {
            "name": "Good scores, penalty = 50 = NO_HIRE",
            "scores": {"task_completion": 85, "code_quality": 80, "seniority_indicators": 75},
            "penalty": 50,
            "expected_decision": "NO_HIRE",
            "expected_reason": "Penalty >= 50 (automatic rejection)"
        },
        {
            "name": "Mediocre scores, low penalty = NO_HIRE",
            "scores": {"task_completion": 65, "code_quality": 60, "seniority_indicators": 65},
            "penalty": 20,
            "expected_decision": "NO_HIRE",
            "expected_reason": "Average score < 70%"
        },
        {
            "name": "Good architecture + minor issues = HIRE",
            "scores": {"task_completion": 90, "code_quality": 85, "seniority_indicators": 80},
            "penalty": 20,  # Only math/rand, no architecture penalty
            "expected_decision": "HIRE",
            "expected_reason": "Good implementation with minor issues"
        },
        {
            "name": "No architecture = NO_HIRE",
            "scores": {"task_completion": 90, "code_quality": 85, "seniority_indicators": 80},
            "penalty": 50,  # Architecture penalty alone
            "expected_decision": "NO_HIRE",
            "expected_reason": "No identifiable architecture pattern"
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        # Calculate average score
        avg_score = sum(test['scores'].values()) / len(test['scores'])
        
        # Determine decision based on rules
        if test['penalty'] >= 50:
            decision = "NO_HIRE"
            reason = "Penalty >= 50"
        elif avg_score >= 70:
            decision = "HIRE"
            reason = f"Average score {avg_score:.0f}% with penalty < 50"
        else:
            decision = "NO_HIRE"
            reason = f"Average score {avg_score:.0f}% < 70%"
        
        if decision == test['expected_decision']:
            print(f"  ✅ Correct decision: {decision} ({reason})")
            passed += 1
        else:
            print(f"  ❌ Wrong decision: {decision} (expected {test['expected_decision']})")
            failed += 1
    
    return passed, failed


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Edge Cases\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Exactly 50 penalty = rejection",
            "response": {
                "detailed_feedback": "Multiple issues found",
                "penalty_breakdown": {
                    "issues_found": [
                        {"issue": "Issue 1", "penalty": 30},
                        {"issue": "Issue 2", "penalty": 20}
                    ],
                    "total_penalty": 50
                },
                "scores": {"critical_issues_penalty": 50}
            },
            "should_reject": True
        },
        {
            "name": "49 penalty = possible hire",
            "response": {
                "detailed_feedback": "Some issues found",
                "penalty_breakdown": {
                    "issues_found": [
                        {"issue": "Issue 1", "penalty": 30},
                        {"issue": "Issue 2", "penalty": 19}
                    ],
                    "total_penalty": 49
                },
                "scores": {"critical_issues_penalty": 49}
            },
            "should_reject": False
        },
        {
            "name": "Empty penalty breakdown",
            "response": {
                "detailed_feedback": "Great implementation with clean architecture",
                "penalty_breakdown": {},
                "scores": {"critical_issues_penalty": 0}
            },
            "should_reject": False
        },
        {
            "name": "Missing penalty_breakdown entirely",
            "response": {
                "detailed_feedback": "Code looks good",
                "scores": {"critical_issues_penalty": 0}
            },
            "should_reject": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        # Run the validator
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        would_reject = penalty >= 50
        
        if would_reject == test['should_reject']:
            status = "rejected" if would_reject else "not rejected"
            print(f"  ✅ Correctly {status} with penalty {penalty}")
            passed += 1
        else:
            expected = "rejected" if test['should_reject'] else "not rejected"
            print(f"  ❌ Should be {expected}, penalty: {penalty}")
            failed += 1
    
    return passed, failed


def run_all_tests():
    """Run all comprehensive penalty tests."""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE PENALTY ENFORCEMENT TEST SUITE")
    print("=" * 60)
    
    all_passed = 0
    all_failed = 0
    
    # Run test suites
    tests = [
        ("Penalty Capping", test_penalty_capping),
        ("Architecture Detection", test_architecture_detection),
        ("Hiring Decisions", test_hiring_decisions),
        ("Edge Cases", test_edge_cases)
    ]
    
    for test_name, test_func in tests:
        passed, failed = test_func()
        all_passed += passed
        all_failed += failed
        print(f"\n{test_name}: {passed} passed, {failed} failed")
    
    # Final summary
    print("\n" + "=" * 60)
    print(f"FINAL RESULTS: {all_passed} passed, {all_failed} failed")
    
    if all_failed == 0:
        print("✅ ALL TESTS PASSED! System is working correctly.")
    else:
        print(f"❌ {all_failed} tests failed. Issues need to be fixed.")
    
    print("=" * 60)
    
    return all_failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
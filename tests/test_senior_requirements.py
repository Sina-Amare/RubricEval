"""
Test suite for mandatory senior-level backend requirements.

This test verifies that submissions are automatically rejected if they lack:
1. Repository pattern
2. Service layer
3. Redis + Database (not just in-memory)
4. Proper Dockerization
"""

import sys
import os
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.analyzers.openrouter import OpenRouterAdapter


def test_repository_pattern_enforcement():
    """Test that missing repository pattern triggers automatic rejection."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Repository Pattern Enforcement\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Missing repository pattern",
            "response": {
                "detailed_feedback": "Code has services but missing repository pattern. Database queries are directly in services.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_reject": True
        },
        {
            "name": "No repository layer abstraction",
            "response": {
                "detailed_feedback": "No repository layer found. Data access is not abstracted properly.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_reject": True
        },
        {
            "name": "Has proper repository pattern",
            "response": {
                "detailed_feedback": "Good implementation with repository pattern properly abstracting data access.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 0,
            "should_reject": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        
        if test['should_reject']:
            if penalty >= test['expected_penalty']:
                print(f"  ✅ Correctly rejected with penalty {penalty}")
                passed += 1
            else:
                print(f"  ❌ Should reject but penalty only {penalty}")
                failed += 1
        else:
            if penalty == test['expected_penalty']:
                print(f"  ✅ Correctly accepted with penalty {penalty}")
                passed += 1
            else:
                print(f"  ❌ Wrong penalty: {penalty} (expected {test['expected_penalty']})")
                failed += 1
    
    return passed, failed


def test_service_layer_enforcement():
    """Test that missing service layer triggers automatic rejection."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Service Layer Enforcement\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Missing service layer",
            "response": {
                "detailed_feedback": "No service layer found. Business logic is mixed with handlers.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_reject": True
        },
        {
            "name": "No service abstraction",
            "response": {
                "detailed_feedback": "Missing service pattern. All logic is in controllers.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_reject": True
        },
        {
            "name": "Has proper service layer",
            "response": {
                "detailed_feedback": "Well-structured with service layer handling business logic separately.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 0,
            "should_reject": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        
        if test['should_reject']:
            if penalty >= test['expected_penalty']:
                print(f"  ✅ Correctly rejected with penalty {penalty}")
                passed += 1
            else:
                print(f"  ❌ Should reject but penalty only {penalty}")
                failed += 1
        else:
            if penalty == test['expected_penalty']:
                print(f"  ✅ Correctly accepted with penalty {penalty}")
                passed += 1
            else:
                print(f"  ❌ Wrong penalty: {penalty} (expected {test['expected_penalty']})")
                failed += 1
    
    return passed, failed


def test_data_storage_requirements():
    """Test that Redis + Database are required (not just in-memory)."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Data Storage Requirements\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Only in-memory storage",
            "response": {
                "detailed_feedback": "Uses only in-memory storage. No Redis or database implementation found.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 50,
            "should_reject": True
        },
        {
            "name": "Missing Redis",
            "response": {
                "detailed_feedback": "Has PostgreSQL database but missing Redis implementation for caching.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 40,
            "should_reject": False  # 40 points, not automatic rejection
        },
        {
            "name": "Missing proper database",
            "response": {
                "detailed_feedback": "Has Redis for caching but no proper database like PostgreSQL or MySQL.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 40,
            "should_reject": False  # 40 points, not automatic rejection
        },
        {
            "name": "Has Redis and database",
            "response": {
                "detailed_feedback": "Properly uses Redis for rate limiting and PostgreSQL for data persistence.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 0,
            "should_reject": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        
        if test['should_reject']:
            if penalty >= 50:
                print(f"  ✅ Correctly rejected with penalty {penalty}")
                passed += 1
            else:
                print(f"  ❌ Should reject but penalty only {penalty}")
                failed += 1
        else:
            if penalty == test['expected_penalty']:
                print(f"  ✅ Correct penalty: {penalty}")
                passed += 1
            else:
                print(f"  ❌ Wrong penalty: {penalty} (expected {test['expected_penalty']})")
                failed += 1
    
    return passed, failed


def test_dockerization_requirements():
    """Test that proper Dockerization is mandatory."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Dockerization Requirements\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Missing Dockerfile",
            "response": {
                "detailed_feedback": "No Dockerfile found in the project.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 40,
            "should_reject": False  # 40 points alone
        },
        {
            "name": "Missing docker-compose",
            "response": {
                "detailed_feedback": "Has Dockerfile but missing docker-compose.yml for orchestration.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 40,
            "should_reject": False  # 40 points alone
        },
        {
            "name": "Incomplete docker-compose",
            "response": {
                "detailed_feedback": "Docker-compose exists but missing Redis and database services.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 30,
            "should_reject": False  # 30 points alone
        },
        {
            "name": "Missing both Dockerfile and docker-compose",
            "response": {
                "detailed_feedback": "Missing Dockerfile and no docker-compose.yml found.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 80,  # 40 + 40
            "should_reject": True  # Total 80 > 50
        },
        {
            "name": "Proper Dockerization",
            "response": {
                "detailed_feedback": "Well dockerized with multi-stage Dockerfile and complete docker-compose including Redis and PostgreSQL.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_penalty": 0,
            "should_reject": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        
        if test['should_reject']:
            if penalty >= 50:
                print(f"  ✅ Correctly rejected with penalty {penalty}")
                passed += 1
            else:
                print(f"  ❌ Should reject but penalty only {penalty}")
                failed += 1
        else:
            # Allow some tolerance for accumulated penalties
            if abs(penalty - test['expected_penalty']) <= 5:
                print(f"  ✅ Correct penalty: {penalty} (expected ~{test['expected_penalty']})")
                passed += 1
            else:
                print(f"  ❌ Wrong penalty: {penalty} (expected {test['expected_penalty']})")
                failed += 1
    
    return passed, failed


def test_combined_requirements():
    """Test combinations of missing requirements."""
    analyzer = OpenRouterAdapter()
    
    print("\n🔍 Testing Combined Requirements\n")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Missing repository + service layer",
            "response": {
                "detailed_feedback": "Missing repository pattern and no service layer found.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_min_penalty": 50,  # Either one alone is 50
            "should_reject": True
        },
        {
            "name": "Only in-memory + no Docker",
            "response": {
                "detailed_feedback": "Only in-memory storage used. Also missing Dockerfile and docker-compose.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_min_penalty": 50,  # In-memory alone is 50
            "should_reject": True
        },
        {
            "name": "Missing Redis + Dockerfile",
            "response": {
                "detailed_feedback": "Missing Redis implementation and no Dockerfile found.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_min_penalty": 80,  # 40 + 40
            "should_reject": True
        },
        {
            "name": "Junior-level submission (multiple issues)",
            "response": {
                "detailed_feedback": "Missing repository pattern, no service layer, only in-memory storage, no Docker setup.",
                "penalty_breakdown": {"issues_found": [], "total_penalty": 0},
                "scores": {"critical_issues_penalty": 0}
            },
            "expected_min_penalty": 50,  # Any one of these is auto-reject
            "should_reject": True
        }
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        print(f"\nTest: {test['name']}")
        
        response_copy = json.loads(json.dumps(test['response']))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        
        if test['should_reject']:
            if penalty >= 50:
                print(f"  ✅ Correctly rejected with penalty {penalty}")
                passed += 1
            else:
                print(f"  ❌ Should reject but penalty only {penalty}")
                failed += 1
        else:
            if penalty >= test['expected_min_penalty']:
                print(f"  ✅ Penalty {penalty} >= {test['expected_min_penalty']}")
                passed += 1
            else:
                print(f"  ❌ Penalty too low: {penalty} (expected >= {test['expected_min_penalty']})")
                failed += 1
    
    return passed, failed


def run_all_tests():
    """Run all senior requirement tests."""
    print("\n" + "=" * 60)
    print("SENIOR-LEVEL REQUIREMENTS TEST SUITE")
    print("=" * 60)
    
    all_passed = 0
    all_failed = 0
    
    tests = [
        ("Repository Pattern", test_repository_pattern_enforcement),
        ("Service Layer", test_service_layer_enforcement),
        ("Data Storage", test_data_storage_requirements),
        ("Dockerization", test_dockerization_requirements),
        ("Combined Requirements", test_combined_requirements)
    ]
    
    for test_name, test_func in tests:
        passed, failed = test_func()
        all_passed += passed
        all_failed += failed
        print(f"\n{test_name}: {passed} passed, {failed} failed")
    
    print("\n" + "=" * 60)
    print(f"FINAL RESULTS: {all_passed} passed, {all_failed} failed")
    
    if all_failed == 0:
        print("✅ ALL SENIOR REQUIREMENT TESTS PASSED!")
        print("\nMandatory requirements enforced:")
        print("1. ✅ Repository pattern (50 penalty if missing)")
        print("2. ✅ Service layer (50 penalty if missing)")
        print("3. ✅ Redis + Database (50 penalty if only in-memory)")
        print("4. ✅ Proper Dockerization (40+40 penalties if missing)")
    else:
        print(f"❌ {all_failed} tests failed")
    
    print("=" * 60)
    
    return all_failed == 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    success = run_all_tests()
    exit(0 if success else 1)
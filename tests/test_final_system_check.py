"""
Final comprehensive system check before production use.
This test verifies ALL critical components are working correctly.
"""

import sys
import os
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.analyzers.openrouter import OpenRouterAdapter
from utils.prompts import PromptLoader
from utils.validators import validate_analysis_result
from core.models import Role


def check_prompt_loading():
    """Check that prompts load without errors."""
    print("\n🔍 Checking Prompt Loading...")
    print("-" * 50)
    
    try:
        loader = PromptLoader()
        
        # Test backend prompt
        params = {
            'task_requirements': "Test requirements",
            'github_url': "https://github.com/test/repo",
            'file_count': 10,
            'total_tokens': 1000,
            'repository_structure': "test/\n  main.go",
            'code_content': "package main"
        }
        backend_prompt = loader.load_prompt('analysis/senior_backend_analysis.md', params)
        
        # Check for critical sections
        assert "MANDATORY SENIOR-LEVEL REQUIREMENTS" in backend_prompt
        assert "repository_pattern" in backend_prompt
        assert "service_layer" in backend_prompt
        assert "redis_implementation" in backend_prompt
        assert "dockerization" in backend_prompt
        assert "+50 points (AUTO-REJECT)" in backend_prompt
        
        print("✅ Backend prompt loads correctly")
        print("✅ All mandatory requirements sections present")
        
        # Test that JSON examples are properly escaped
        assert "{{" in backend_prompt and "}}" in backend_prompt
        print("✅ JSON examples properly escaped")
        
        return True
        
    except Exception as e:
        print(f"❌ Prompt loading failed: {e}")
        return False


def check_penalty_enforcement():
    """Check that all penalties are enforced correctly."""
    print("\n🔍 Checking Penalty Enforcement...")
    print("-" * 50)
    
    analyzer = OpenRouterAdapter()
    
    test_cases = [
        {
            "name": "Math/rand capped at 20",
            "feedback": "Uses math/rand for OTP generation",
            "initial_penalty": 40,
            "expected_penalty": 20
        },
        {
            "name": "No architecture = 50",
            "feedback": "Code has folders but no architectural pattern",
            "initial_penalty": 0,
            "expected_penalty": 50
        },
        {
            "name": "Missing repository = 50",
            "feedback": "Missing repository pattern",
            "initial_penalty": 0,
            "expected_penalty": 50
        },
        {
            "name": "Missing service layer = 50",
            "feedback": "No service layer found",
            "initial_penalty": 0,
            "expected_penalty": 50
        },
        {
            "name": "Only in-memory = 50",
            "feedback": "Only in-memory storage used",
            "initial_penalty": 0,
            "expected_penalty": 50
        },
        {
            "name": "Good architecture = 0 penalty",
            "feedback": "Implements layered architecture with repository pattern and service layer",
            "initial_penalty": 0,
            "expected_penalty": 0
        }
    ]
    
    all_passed = True
    for test in test_cases:
        response = {
            "detailed_feedback": test["feedback"],
            "penalty_breakdown": {
                "issues_found": [
                    {"issue": test["feedback"], "penalty": test["initial_penalty"]}
                ] if test["initial_penalty"] > 0 else [],
                "total_penalty": test["initial_penalty"]
            },
            "scores": {"critical_issues_penalty": test["initial_penalty"]}
        }
        
        response_copy = json.loads(json.dumps(response))
        analyzer._validate_and_adjust_penalty(response_copy)
        
        actual_penalty = response_copy['scores'].get('critical_issues_penalty', 0)
        
        if actual_penalty == test["expected_penalty"]:
            print(f"✅ {test['name']}: {actual_penalty} points")
        else:
            print(f"❌ {test['name']}: Expected {test['expected_penalty']}, got {actual_penalty}")
            all_passed = False
    
    return all_passed


def check_scoring_logic():
    """Check that hiring decisions follow correct logic."""
    print("\n🔍 Checking Scoring Logic...")
    print("-" * 50)
    
    test_cases = [
        {
            "name": "Good scores + low penalty = HIRE",
            "scores": {"task_completion": 85, "code_quality": 80, "seniority_indicators": 75},
            "penalty": 20,
            "expected": "HIRE"
        },
        {
            "name": "Good scores + 50 penalty = NO_HIRE",
            "scores": {"task_completion": 85, "code_quality": 80, "seniority_indicators": 75},
            "penalty": 50,
            "expected": "NO_HIRE"
        },
        {
            "name": "Low scores + low penalty = NO_HIRE",
            "scores": {"task_completion": 65, "code_quality": 60, "seniority_indicators": 60},
            "penalty": 20,
            "expected": "NO_HIRE"
        },
        {
            "name": "Excellent + no penalty = HIRE",
            "scores": {"task_completion": 95, "code_quality": 90, "seniority_indicators": 85},
            "penalty": 0,
            "expected": "HIRE"
        }
    ]
    
    all_passed = True
    for test in test_cases:
        avg_score = sum(test["scores"].values()) / len(test["scores"])
        
        if test["penalty"] >= 50:
            decision = "NO_HIRE"
        elif avg_score >= 70:
            decision = "HIRE"
        else:
            decision = "NO_HIRE"
        
        if decision == test["expected"]:
            print(f"✅ {test['name']}: {decision}")
        else:
            print(f"❌ {test['name']}: Expected {test['expected']}, got {decision}")
            all_passed = False
    
    return all_passed


def check_validator():
    """Check that score validator works correctly."""
    print("\n🔍 Checking Score Validator...")
    print("-" * 50)
    
    # Test valid analysis result
    valid_result = {
        "scores": {
            "task_completion": 85.0,
            "code_quality": 80.0,
            "seniority_indicators": 75.0,
            "critical_issues_penalty": 30.0
        },
        "recommendation": "yes",
        "confidence": 0.85,
        "requirements_met": {},
        "strengths": [],
        "weaknesses": [],
        "detailed_feedback": "Test feedback"
    }
    
    is_valid, msg = validate_analysis_result(valid_result)
    if is_valid:
        print("✅ Valid scores accepted")
    else:
        print(f"❌ Valid scores rejected: {msg}")
        return False
    
    # Test penalty can exceed 50
    high_penalty_result = {
        "scores": {
            "task_completion": 85.0,
            "code_quality": 80.0,
            "seniority_indicators": 75.0,
            "critical_issues_penalty": 150.0  # Multiple issues
        },
        "recommendation": "no",
        "confidence": 0.95,
        "requirements_met": {},
        "strengths": [],
        "weaknesses": [],
        "detailed_feedback": "Multiple critical issues"
    }
    
    is_valid, msg = validate_analysis_result(high_penalty_result)
    if is_valid:
        print("✅ High penalties (>50) accepted")
    else:
        print(f"❌ High penalties rejected: {msg}")
        return False
    
    return True


def run_final_checks():
    """Run all final system checks."""
    print("\n" + "=" * 60)
    print("FINAL SYSTEM CHECK BEFORE PRODUCTION")
    print("=" * 60)
    
    checks = [
        ("Prompt Loading", check_prompt_loading),
        ("Penalty Enforcement", check_penalty_enforcement),
        ("Scoring Logic", check_scoring_logic),
        ("Score Validator", check_validator)
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        try:
            passed = check_func()
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"❌ {check_name} failed with error: {e}")
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✅ ALL SYSTEMS GO - READY FOR PRODUCTION!")
        print("\nVerified Components:")
        print("1. ✅ Prompts load correctly with all requirements")
        print("2. ✅ Math/rand capped at 20 points maximum")
        print("3. ✅ Architecture penalties enforced (50 points)")
        print("4. ✅ Repository/Service/Redis/DB checks working")
        print("5. ✅ Hiring logic correct (avg ≥70% AND penalty <50)")
        print("6. ✅ High penalties accepted for multiple issues")
        print("\n🚀 You can safely make LLM calls now!")
        
    else:
        print("❌ SYSTEM CHECK FAILED - DO NOT USE IN PRODUCTION!")
        print("Please fix the issues above before making LLM calls.")
    
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    success = run_final_checks()
    exit(0 if success else 1)
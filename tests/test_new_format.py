#!/usr/bin/env python3
"""Test script to verify new prompt format handling."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from adapters.analyzers.openrouter import OpenRouterAdapter
from core.models import AnalysisResult, RecommendationLevel
from utils.validators import validate_analysis_result
import json

# Sample response in new format
new_format_response = {
    "task_analysis": {
        "explicit_requirements": ["Create login page", "Phone validation"],
        "implicit_requirements": ["Error handling", "Loading states"],
        "not_required": ["OAuth", "Password reset"],
        "task_complexity": "simple"
    },
    "requirements_implementation": {
        "login_form": {
            "requested": True,
            "implemented": True,
            "quality": "good",
            "notes": "Form implemented with validation"
        },
        "phone_validation": {
            "requested": True,
            "implemented": True,
            "quality": "excellent",
            "notes": "Proper regex validation for Iranian numbers"
        }
    },
    "critical_issues": [],
    "seniority_assessment": {
        "level_demonstrated": "mid",
        "strengths": [
            "Clean code structure",
            "Proper state management",
            "Good error handling"
        ],
        "growth_areas": [
            "Could add more comprehensive testing",
            "Performance optimizations possible"
        ],
        "evidence": ["Uses hooks properly", "Implements loading states"]
    },
    "code_quality": {
        "readability": "good",
        "organization": "good",
        "error_handling": "good",
        "performance_awareness": True,
        "security_awareness": True
    },
    "scores": {
        "task_completion": 85,
        "code_quality": 80,
        "seniority_indicators": 75,
        "critical_issues_penalty": 100
    },
    "recommendation": "yes",
    "confidence": 0.85,
    "hiring_decision": {
        "decision": "HIRE",
        "primary_reason": "Completed all requirements with good quality",
        "is_task_appropriate": "Yes, delivered what was asked",
        "is_production_ready": "Yes, with minor tweaks"
    },
    "detailed_feedback": "The candidate successfully implemented the login page with proper phone validation. The code shows good understanding of React patterns and state management."
}

# Sample response in old format for comparison
old_format_response = {
    "requirements_met": {
        "login_form": True,
        "phone_validation": True
    },
    "scores": {
        "completeness": 85,
        "quality": 80,
        "architecture": 75,
        "testing": 70
    },
    "strengths": [
        "Clean code structure",
        "Good error handling"
    ],
    "weaknesses": [
        "No tests included",
        "Could improve performance"
    ],
    "recommendation": "yes",
    "confidence": 0.85,
    "detailed_feedback": "Good implementation overall"
}

async def test_validation():
    """Test that validation works for both formats."""
    print("Testing validation...")
    
    # Test new format
    is_valid, error = validate_analysis_result(new_format_response)
    print(f"New format valid: {is_valid}")
    if error:
        print(f"  Error: {error}")
    
    # Test old format
    is_valid, error = validate_analysis_result(old_format_response)
    print(f"Old format valid: {is_valid}")
    if error:
        print(f"  Error: {error}")

async def test_analysis_result_creation():
    """Test that AnalysisResult can be created from new format."""
    print("\nTesting AnalysisResult creation...")
    
    try:
        # Initialize adapter
        adapter = OpenRouterAdapter()
        
        # Process new format response
        result = adapter._convert_to_analysis_result(new_format_response)
        
        print(f"Created AnalysisResult successfully!")
        print(f"  Recommendation: {result.recommendation}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Scores: {result.scores}")
        print(f"  Strengths count: {len(result.strengths)}")
        print(f"  Weaknesses count: {len(result.weaknesses)}")
        print(f"  Requirements met: {result.requirements_met}")
        
        # Verify recommendation mapping
        if result.recommendation == RecommendationLevel.ACCEPT:
            print("  ✓ Recommendation correctly mapped to ACCEPT")
        else:
            print(f"  ✗ Recommendation incorrectly mapped to {result.recommendation}")
            
    except Exception as e:
        print(f"Failed to create AnalysisResult: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all tests."""
    await test_validation()
    await test_analysis_result_creation()
    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
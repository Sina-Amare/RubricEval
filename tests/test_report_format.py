"""
Test the updated report format with senior-level architecture requirements.
"""

import sys
import os
import asyncio
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.notifications.telegram import TelegramAdapter
from core.models import (
    Submission, Report, AnalysisResult, Role, 
    SubmissionStatus, RecommendationLevel
)


def create_test_submission():
    """Create a test submission."""
    return Submission(
        id=1,
        telegram_user_id="123456",
        telegram_username="testuser",
        github_url="https://github.com/test/repo",
        role=Role.BACKEND,
        status=SubmissionStatus.COMPLETED,
        created_at=datetime.now(timezone.utc)
    )


def create_test_report_with_good_architecture():
    """Create a test report with good architecture."""
    analysis_result = AnalysisResult(
        requirements_met={
            "otp_login_registration": True,
            "rate_limiting": True,
            "user_management": True,
            "api_documentation": True,
            "architectural_pattern": True,
            "repository_pattern": True,
            "service_layer": True,
            "redis_implementation": True,
            "database_implementation": True,
            "dockerization": True
        },
        scores={
            "task_completion": 95.0,
            "code_quality": 85.0,
            "seniority_indicators": 80.0,
            "critical_issues_penalty": 20.0
        },
        recommendation=RecommendationLevel.ACCEPT,
        confidence=0.9,
        strengths=[
            "Clear layered architecture with proper separation",
            "Repository pattern implemented correctly",
            "Service layer handles business logic",
            "Redis used for rate limiting",
            "PostgreSQL for data persistence"
        ],
        weaknesses=[
            "Using math/rand for OTP generation"
        ],
        detailed_feedback="Excellent implementation with layered architecture pattern. Repository and service layers are properly separated. Uses Redis for rate limiting and PostgreSQL for persistence. Docker setup is complete with multi-stage builds.",
        hiring_decision={
            "decision": "HIRE",
            "primary_reason": "Strong senior-level implementation with proper architecture"
        },
        penalty_breakdown={
            "issues_found": [
                {"issue": "Using math/rand for OTP", "severity": "moderate", "penalty": 20}
            ],
            "total_penalty": 20
        }
    )
    
    return Report(
        id=1,
        submission_id=1,
        analysis_result=analysis_result,
        model_used="gemini-2.5-flash",
        tokens_used=5000,
        analysis_duration=10.5,
        created_at=datetime.now(timezone.utc)
    )


def create_test_report_missing_architecture():
    """Create a test report missing architecture requirements."""
    analysis_result = AnalysisResult(
        requirements_met={
            "otp_login_registration": True,
            "rate_limiting": True,
            "user_management": True,
            "api_documentation": False,
            "architectural_pattern": False,
            "repository_pattern": False,
            "service_layer": False,
            "redis_implementation": False,
            "database_implementation": False,
            "dockerization": False
        },
        scores={
            "task_completion": 70.0,
            "code_quality": 60.0,
            "seniority_indicators": 50.0,
            "critical_issues_penalty": 150.0
        },
        recommendation=RecommendationLevel.REJECT,
        confidence=0.95,
        strengths=[
            "Basic functionality works"
        ],
        weaknesses=[
            "No architectural pattern identified",
            "Missing repository pattern",
            "No service layer",
            "Only in-memory storage",
            "No Docker setup"
        ],
        detailed_feedback="Code has folders but no architectural pattern. Missing repository pattern and service layer. Only uses in-memory storage with no Redis or database. No Dockerfile or docker-compose found.",
        hiring_decision={
            "decision": "NO_HIRE",
            "primary_reason": "Not senior-level - missing fundamental architecture"
        },
        penalty_breakdown={
            "issues_found": [
                {"issue": "[ENFORCED] No identifiable architecture pattern", "severity": "critical", "penalty": 50},
                {"issue": "[ENFORCED] Missing repository pattern", "severity": "critical", "penalty": 50},
                {"issue": "[ENFORCED] Missing service layer", "severity": "critical", "penalty": 50}
            ],
            "total_penalty": 150
        }
    )
    
    return Report(
        id=2,
        submission_id=2,
        analysis_result=analysis_result,
        model_used="gemini-2.5-flash",
        tokens_used=5000,
        analysis_duration=10.5,
        created_at=datetime.now(timezone.utc)
    )


async def test_report_format():
    """Test the report format with architecture requirements."""
    
    # Initialize adapter (without actual bot token)
    adapter = TelegramAdapter(bot_token="test_token")
    
    print("\n" + "=" * 60)
    print("TESTING REPORT FORMAT WITH ARCHITECTURE REQUIREMENTS")
    print("=" * 60)
    
    # Test 1: Good architecture report
    print("\n📊 Test 1: Good Architecture Implementation")
    print("-" * 60)
    
    submission1 = create_test_submission()
    report1 = create_test_report_with_good_architecture()
    
    # Format the report (this is the internal method)
    report_text = adapter._format_analysis_report(submission1, report1)
    
    # Check for key sections
    assert "TASK REQUIREMENTS CHECK" in report_text, "Missing task requirements section"
    assert "SENIOR-LEVEL ARCHITECTURE CHECK" in report_text, "Missing architecture check section"
    
    # Check for specific requirements
    assert "otp_login_registration" in report_text, "Missing OTP requirement"
    assert "Architectural Pattern" in report_text, "Missing architecture pattern check"
    assert "Repository Pattern" in report_text, "Missing repository pattern check"
    assert "Service Layer" in report_text, "Missing service layer check"
    assert "Redis Implementation" in report_text, "Missing Redis check"
    assert "Database" in report_text, "Missing database check"
    assert "Dockerization" in report_text, "Missing Docker check"
    
    print("✅ Report includes all architecture checks")
    print("\nSample architecture section:")
    # Extract and print architecture section
    if "SENIOR-LEVEL ARCHITECTURE CHECK" in report_text:
        start = report_text.index("SENIOR-LEVEL ARCHITECTURE CHECK")
        end = report_text.index("DETAILED FEEDBACK", start)
        arch_section = report_text[start:end].strip()
        # Remove HTML tags for display
        arch_section = arch_section.replace('<b>', '').replace('</b>', '')
        arch_section = arch_section.replace('<code>', '').replace('</code>', '')
        print(arch_section[:500])  # Print first 500 chars
    
    # Test 2: Missing architecture report
    print("\n📊 Test 2: Missing Architecture Requirements")
    print("-" * 60)
    
    submission2 = create_test_submission()
    submission2.id = 2
    report2 = create_test_report_missing_architecture()
    
    report_text2 = adapter._format_analysis_report(submission2, report2)
    
    # Check for failure indicators
    assert "✗" in report_text2, "Missing failure indicators"
    assert "AUTO-REJECT" in report_text2, "Missing auto-reject threshold"
    assert "[ENFORCED]" in report_text2, "Missing enforced penalties"
    
    print("✅ Report shows architecture failures correctly")
    print("\nSample failure section:")
    if "CRITICAL ISSUES BREAKDOWN" in report_text2:
        start = report_text2.index("CRITICAL ISSUES BREAKDOWN")
        end = report_text2.index("STRENGTHS", start) if "STRENGTHS" in report_text2[start:] else start + 500
        issues_section = report_text2[start:end].strip()
        # Remove HTML tags for display
        issues_section = issues_section.replace('<b>', '').replace('</b>', '')
        issues_section = issues_section.replace('<code>', '').replace('</code>', '')
        print(issues_section[:500])  # Print first 500 chars
    
    print("\n" + "=" * 60)
    print("✅ ALL REPORT FORMAT TESTS PASSED")
    print("=" * 60)
    print("\nKey features verified:")
    print("1. ✅ Task requirements section included")
    print("2. ✅ Senior-level architecture checks section added")
    print("3. ✅ All 6 architecture requirements displayed")
    print("4. ✅ Pass/Fail status clearly shown")
    print("5. ✅ Critical issues with penalties displayed")
    print("6. ✅ Auto-reject threshold indicated")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_report_format())
    exit(0 if success else 1)
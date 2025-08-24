"""
Test suite for core domain models.

This module tests the core business entities and their behaviors.
"""

import sys
import os
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.models import (
    SubmissionStatus,
    Role,
    RecommendationLevel,
    FileInfo,
    RepositoryContent,
    AnalysisRequest,
    AnalysisResult,
    Submission,
    Report
)


def test_file_info():
    """Test FileInfo model."""
    print("\n=== Testing FileInfo ===")
    
    # Create a file info instance
    file = FileInfo(
        path="src/main.go",
        content="package main\n\nfunc main() {}",
        priority="critical",
        tokens=15,
        language="go"
    )
    
    # Test attributes
    assert file.path == "src/main.go"
    assert file.priority == "critical"
    assert file.tokens == 15
    assert file.language == "go"
    
    print(f"✓ FileInfo created: {file}")
    print("✓ All FileInfo tests passed")


def test_repository_content():
    """Test RepositoryContent model."""
    print("\n=== Testing RepositoryContent ===")
    
    # Create files
    files = [
        FileInfo("main.go", "content1", "critical", 100, "go"),
        FileInfo("auth.go", "content2", "critical", 150, "go"),
        FileInfo("test.go", "content3", "important", 80, "go"),
        FileInfo("README.md", "content4", "useful", 50, "markdown")
    ]
    
    # Create repository content
    repo = RepositoryContent(
        url="https://github.com/test/repo",
        files=files,
        total_tokens=380,
        structure="Project structure here",
        metadata={"stars": 100, "language": "Go"}
    )
    
    # Test methods
    critical_files = repo.get_critical_files()
    assert len(critical_files) == 2
    print(f"✓ Found {len(critical_files)} critical files")
    
    go_files = repo.get_files_by_language("go")
    assert len(go_files) == 3
    print(f"✓ Found {len(go_files)} Go files")
    
    print("✓ All RepositoryContent tests passed")


def test_analysis_result():
    """Test AnalysisResult model."""
    print("\n=== Testing AnalysisResult ===")
    
    # Create analysis result
    result = AnalysisResult(
        requirements_met={
            "OTP Implementation": True,
            "Rate Limiting": True,
            "JWT Tokens": False
        },
        scores={
            "Code Quality": 0.85,
            "Architecture": 0.90,
            "Testing": 0.60
        },
        recommendation=RecommendationLevel.ACCEPT,
        confidence=0.80,
        strengths=["Clean code", "Good architecture", "Proper error handling"],
        weaknesses=["Missing tests", "No JWT implementation"],
        detailed_feedback="Overall good implementation with room for improvement",
        suggestions=["Add unit tests", "Implement JWT tokens"]
    )
    
    # Test methods
    overall_score = result.get_overall_score()
    assert 0.78 < overall_score < 0.79  # Should be ~0.783
    print(f"✓ Overall score calculated: {overall_score:.2%}")
    
    # Test dictionary conversion
    result_dict = result.to_dict()
    assert result_dict["recommendation"] == "accept"
    assert len(result_dict["strengths"]) == 3
    print("✓ Converted to dictionary successfully")
    
    print("✓ All AnalysisResult tests passed")


def test_submission():
    """Test Submission model."""
    print("\n=== Testing Submission ===")
    
    # Create submission
    submission = Submission(
        telegram_user_id="123456789",
        telegram_username="testuser",
        github_url="https://github.com/test/repo",
        role=Role.BACKEND
    )
    
    # Test defaults
    assert submission.status == SubmissionStatus.PENDING
    assert submission.created_at is not None
    assert submission.updated_at is not None
    print(f"✓ Submission created with status: {submission.status.value}")
    
    # Test methods
    assert not submission.is_complete()
    print("✓ Submission is not complete (as expected)")
    
    # Update status
    submission.status = SubmissionStatus.FAILED
    submission.error_message = "Test error"
    
    assert submission.is_complete()
    assert submission.can_retry()
    print("✓ Failed submission can be retried")
    
    print("✓ All Submission tests passed")


def test_report():
    """Test Report model."""
    print("\n=== Testing Report ===")
    
    # Create analysis result
    analysis_result = AnalysisResult(
        requirements_met={"Req1": True},
        scores={"Quality": 0.9},
        recommendation=RecommendationLevel.STRONGLY_ACCEPT,
        confidence=0.95,
        strengths=["Excellent"],
        weaknesses=[],
        detailed_feedback="Perfect implementation"
    )
    
    # Create report
    report = Report(
        submission_id=1,
        analysis_result=analysis_result,
        model_used="gpt-4",
        tokens_used=5000,
        analysis_duration=45.5
    )
    
    # Test attributes
    assert report.created_at is not None
    assert report.model_used == "gpt-4"
    print(f"✓ Report created with model: {report.model_used}")
    
    # Test summary generation
    summary = report.get_summary()
    assert "Strongly Accept" in summary
    assert "95.0%" in summary  # Confidence
    assert "45.5s" in summary  # Duration
    print("✓ Report summary generated")
    
    # Test dictionary conversion
    report_dict = report.to_dict()
    assert report_dict["tokens_used"] == 5000
    assert report_dict["analysis_result"]["recommendation"] == "strongly_accept"
    print("✓ Converted to dictionary successfully")
    
    print("✓ All Report tests passed")


def test_enums():
    """Test enum values."""
    print("\n=== Testing Enums ===")
    
    # Test SubmissionStatus
    assert SubmissionStatus.PENDING.value == "pending"
    assert SubmissionStatus.COMPLETED.value == "completed"
    print("✓ SubmissionStatus enum values correct")
    
    # Test Role
    assert Role.BACKEND.value == "backend"
    assert Role.FRONTEND.value == "frontend"
    print("✓ Role enum values correct")
    
    # Test RecommendationLevel
    assert RecommendationLevel.STRONGLY_ACCEPT.value == "strongly_accept"
    assert RecommendationLevel.REJECT.value == "reject"
    print("✓ RecommendationLevel enum values correct")
    
    print("✓ All Enum tests passed")


def run_all_tests():
    """Run all test functions."""
    print("=" * 50)
    print("RUNNING CORE MODEL TESTS")
    print("=" * 50)
    
    try:
        test_enums()
        test_file_info()
        test_repository_content()
        test_analysis_result()
        test_submission()
        test_report()
        
        print("\n" + "=" * 50)
        print("✅ ALL CORE MODEL TESTS PASSED!")
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


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
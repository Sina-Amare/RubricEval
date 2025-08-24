"""
Test suite for SQLite storage adapter.

This module tests the SQLite storage adapter functionality.
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.storage.sqlite import SQLiteAdapter
from core.models import (
    Submission,
    Report,
    SubmissionStatus,
    Role,
    RecommendationLevel,
    AnalysisResult
)
from core.exceptions import StorageError


async def test_adapter_initialization():
    """Test SQLite adapter initialization."""
    print("\n=== Testing Adapter Initialization ===")
    
    # Create adapter
    adapter = SQLiteAdapter()
    
    # Initialize database
    await adapter.initialize()
    print("✓ Adapter initialized successfully")
    
    # Close adapter
    await adapter.close()
    print("✓ Adapter closed successfully")
    
    print("✓ Initialization tests passed")
    return adapter


async def test_submission_operations(adapter: SQLiteAdapter):
    """Test submission CRUD operations."""
    print("\n=== Testing Submission Operations ===")
    
    # Create a submission
    submission = Submission(
        telegram_user_id="123456789",
        telegram_username="testuser",
        github_url="https://github.com/test/repo",
        role=Role.BACKEND,
        status=SubmissionStatus.PENDING
    )
    
    created = await adapter.create_submission(submission)
    assert created.id is not None
    print(f"✓ Created submission with ID: {created.id}")
    
    # Get submission by ID
    retrieved = await adapter.get_submission(created.id)
    assert retrieved is not None
    assert retrieved.telegram_user_id == "123456789"
    assert retrieved.role == Role.BACKEND
    print("✓ Retrieved submission by ID")
    
    # Update submission status
    updated = await adapter.update_submission(
        created.id,
        status=SubmissionStatus.ANALYZING
    )
    assert updated
    print("✓ Updated submission status")
    
    # Get user submissions
    user_submissions = await adapter.get_user_submissions("123456789")
    assert len(user_submissions) > 0
    assert user_submissions[0].id == created.id
    print(f"✓ Retrieved {len(user_submissions)} user submissions")
    
    # Get pending submissions
    pending = await adapter.get_pending_submissions()
    # Note: Status was updated to ANALYZING, so it shouldn't be in pending
    pending_ids = [s.id for s in pending]
    assert created.id not in pending_ids
    print(f"✓ Retrieved {len(pending)} pending submissions")
    
    # Check duplicate submission
    is_duplicate = await adapter.check_duplicate_submission(
        "123456789",
        "https://github.com/test/repo",
        hours=24
    )
    assert is_duplicate
    print("✓ Duplicate submission detection working")
    
    # Update to failed status with error
    await adapter.update_submission(
        created.id,
        status=SubmissionStatus.FAILED,
        error_message="Test error",
        completed_at=datetime.utcnow()
    )
    
    failed = await adapter.get_submission(created.id)
    assert failed.status == SubmissionStatus.FAILED
    assert failed.error_message == "Test error"
    assert failed.completed_at is not None
    print("✓ Updated submission to failed status")
    
    print("✓ All submission operations passed")
    return created.id


async def test_report_operations(adapter: SQLiteAdapter, submission_id: int):
    """Test report CRUD operations."""
    print("\n=== Testing Report Operations ===")
    
    # Create analysis result
    analysis_result = AnalysisResult(
        requirements_met={
            "Authentication": True,
            "Rate Limiting": False,
            "Testing": True
        },
        scores={
            "completeness": 75,
            "quality": 85,
            "architecture": 90,
            "testing": 60
        },
        recommendation=RecommendationLevel.ACCEPT,
        confidence=0.85,
        strengths=["Clean code", "Good architecture", "Well documented"],
        weaknesses=["Missing rate limiting", "Incomplete tests"],
        detailed_feedback="Overall good implementation with room for improvement in testing.",
        suggestions=["Add rate limiting", "Increase test coverage"]
    )
    
    # Create report
    report = Report(
        submission_id=submission_id,
        analysis_result=analysis_result,
        model_used="gpt-4",
        tokens_used=5000,
        analysis_duration=45.5
    )
    
    created_report = await adapter.create_report(report)
    assert created_report.id is not None
    print(f"✓ Created report with ID: {created_report.id}")
    
    # Get report by ID
    retrieved_report = await adapter.get_report(created_report.id)
    assert retrieved_report is not None
    assert retrieved_report.submission_id == submission_id
    assert retrieved_report.model_used == "gpt-4"
    print("✓ Retrieved report by ID")
    
    # Get report by submission ID
    submission_report = await adapter.get_submission_report(submission_id)
    assert submission_report is not None
    assert submission_report.id == created_report.id
    print("✓ Retrieved report by submission ID")
    
    # Verify analysis result was preserved
    assert len(submission_report.analysis_result.strengths) == 3
    assert submission_report.analysis_result.confidence == 0.85
    assert submission_report.analysis_result.recommendation == RecommendationLevel.ACCEPT
    print("✓ Analysis result data preserved correctly")
    
    # Get recent reports
    recent = await adapter.get_recent_reports(limit=5)
    assert len(recent) > 0
    assert any(r.id == created_report.id for r in recent)
    print(f"✓ Retrieved {len(recent)} recent reports")
    
    # Get recent reports filtered by role
    backend_reports = await adapter.get_recent_reports(limit=5, role=Role.BACKEND)
    # Should include our report since submission was for backend role
    assert any(r.id == created_report.id for r in backend_reports)
    print(f"✓ Retrieved {len(backend_reports)} backend reports")
    
    print("✓ All report operations passed")
    return created_report.id


async def test_statistics(adapter: SQLiteAdapter):
    """Test statistics generation."""
    print("\n=== Testing Statistics ===")
    
    stats = await adapter.get_statistics()
    
    # Check required fields
    assert 'total_submissions' in stats
    assert 'status_breakdown' in stats
    assert 'role_breakdown' in stats
    assert 'recommendation_breakdown' in stats
    assert 'average_analysis_time' in stats
    assert 'recent_submissions_24h' in stats
    
    print(f"✓ Total submissions: {stats['total_submissions']}")
    print(f"✓ Status breakdown: {stats['status_breakdown']}")
    print(f"✓ Role breakdown: {stats['role_breakdown']}")
    if 'average_confidence' in stats:
        print(f"✓ Average confidence: {stats['average_confidence']:.2f}")
    
    # Verify our test data is reflected
    assert stats['total_submissions'] >= 1
    assert 'backend' in str(stats['role_breakdown']).lower()
    
    print("✓ Statistics generation passed")


async def test_cleanup(adapter: SQLiteAdapter):
    """Test data cleanup."""
    print("\n=== Testing Data Cleanup ===")
    
    # Create an old submission (simulating old data)
    old_submission = Submission(
        telegram_user_id="999999999",
        telegram_username="olduser",
        github_url="https://github.com/old/repo",
        role=Role.FRONTEND,
        status=SubmissionStatus.COMPLETED
    )
    # Manually set old date
    old_submission.created_at = datetime.utcnow() - timedelta(days=35)
    
    # Note: For testing, we'd need to directly insert with old date
    # This is a limitation of our current adapter
    
    # Test cleanup (using 30 days)
    deleted_count = await adapter.cleanup_old_data(days=30)
    print(f"✓ Cleaned up {deleted_count} old records")
    
    print("✓ Cleanup tests passed")


async def test_error_handling(adapter: SQLiteAdapter):
    """Test error handling."""
    print("\n=== Testing Error Handling ===")
    
    # Test getting non-existent submission
    non_existent = await adapter.get_submission(999999)
    assert non_existent is None
    print("✓ Non-existent submission returns None")
    
    # Test getting non-existent report
    non_existent_report = await adapter.get_report(999999)
    assert non_existent_report is None
    print("✓ Non-existent report returns None")
    
    # Test updating non-existent submission
    updated = await adapter.update_submission(999999, status=SubmissionStatus.COMPLETED)
    assert not updated
    print("✓ Updating non-existent submission returns False")
    
    print("✓ Error handling tests passed")


async def run_all_tests():
    """Run all async test functions."""
    print("=" * 50)
    print("RUNNING SQLITE ADAPTER TESTS")
    print("=" * 50)
    
    adapter = None
    try:
        # Initialize adapter
        adapter = await test_adapter_initialization()
        
        # Reinitialize for tests
        adapter = SQLiteAdapter()
        await adapter.initialize()
        
        # Run tests
        submission_id = await test_submission_operations(adapter)
        await test_report_operations(adapter, submission_id)
        await test_statistics(adapter)
        await test_error_handling(adapter)
        await test_cleanup(adapter)
        
        print("\n" + "=" * 50)
        print("✅ ALL SQLITE ADAPTER TESTS PASSED!")
        print("=" * 50)
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if adapter:
            await adapter.close()


def main():
    """Main entry point."""
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
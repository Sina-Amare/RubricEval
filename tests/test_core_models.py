"""
Tests for core domain models.

This module tests the core business entities and value objects
used throughout the CV Review Bot application.
"""

import pytest
from datetime import datetime, timezone
from core.models import (
    Submission, Report, AnalysisRequest, AnalysisResult,
    RepositoryContent, FileInfo, Role, SubmissionStatus, 
    RecommendationLevel
)


@pytest.mark.unit
class TestFileInfo:
    """Test FileInfo value object."""
    
    def test_file_info_creation(self):
        """Test basic FileInfo creation."""
        file_info = FileInfo(
            path="src/main.py",
            content="print('Hello, World!')",
            priority="critical",
            tokens=10,
            language="python"
        )
        
        assert file_info.path == "src/main.py"
        assert file_info.content == "print('Hello, World!')"
        assert file_info.priority == "critical"
        assert file_info.tokens == 10
        assert file_info.language == "python"
    
    def test_file_info_defaults(self):
        """Test FileInfo with default values."""
        file_info = FileInfo(
            path="test.txt",
            content="test content"
        )
        
        assert file_info.priority == "useful"
        assert file_info.tokens == 0
        assert file_info.language is None
    
    def test_file_info_repr(self):
        """Test FileInfo string representation."""
        file_info = FileInfo(
            path="test.py",
            content="code",
            priority="important",
            tokens=50
        )
        
        repr_str = repr(file_info)
        assert "test.py" in repr_str
        assert "important" in repr_str
        assert "50" in repr_str


@pytest.mark.unit
class TestRepositoryContent:
    """Test RepositoryContent aggregate."""
    
    def test_repository_content_creation(self, sample_file_info):
        """Test basic RepositoryContent creation."""
        repo_content = RepositoryContent(
            url="https://github.com/test/repo",
            files=[sample_file_info],
            total_tokens=100,
            structure="src/\n  main.py",
            metadata={"branch": "main"}
        )
        
        assert repo_content.url == "https://github.com/test/repo"
        assert len(repo_content.files) == 1
        assert repo_content.total_tokens == 100
        assert repo_content.structure == "src/\n  main.py"
        assert repo_content.metadata["branch"] == "main"
    
    def test_get_critical_files(self):
        """Test getting critical priority files."""
        critical_file = FileInfo(
            path="critical.py",
            content="critical code",
            priority="critical"
        )
        important_file = FileInfo(
            path="important.py", 
            content="important code",
            priority="important"
        )
        
        repo_content = RepositoryContent(
            url="https://github.com/test/repo",
            files=[critical_file, important_file],
            total_tokens=50,
            structure="test"
        )
        
        critical_files = repo_content.get_critical_files()
        assert len(critical_files) == 1
        assert critical_files[0].path == "critical.py"
    
    def test_get_files_by_language(self):
        """Test getting files by language."""
        python_file = FileInfo(
            path="app.py",
            content="python code",
            language="python"
        )
        js_file = FileInfo(
            path="app.js",
            content="javascript code", 
            language="javascript"
        )
        
        repo_content = RepositoryContent(
            url="https://github.com/test/repo",
            files=[python_file, js_file],
            total_tokens=50,
            structure="test"
        )
        
        python_files = repo_content.get_files_by_language("python")
        assert len(python_files) == 1
        assert python_files[0].path == "app.py"
        
        js_files = repo_content.get_files_by_language("javascript")
        assert len(js_files) == 1
        assert js_files[0].path == "app.js"


@pytest.mark.unit
class TestAnalysisResult:
    """Test AnalysisResult value object."""
    
    def test_analysis_result_creation(self, sample_analysis_result):
        """Test basic AnalysisResult creation."""
        result = sample_analysis_result
        
        assert result.recommendation == RecommendationLevel.ACCEPT
        assert result.confidence == 0.85
        assert len(result.strengths) == 3
        assert len(result.weaknesses) == 3
        assert result.scores["task_completion"] == 75.0
        assert result.requirements_met["architectural_pattern"] is True
    
    def test_to_dict_conversion(self, sample_analysis_result):
        """Test converting AnalysisResult to dictionary."""
        result_dict = sample_analysis_result.to_dict()
        
        assert result_dict["recommendation"] == "accept"
        assert result_dict["confidence"] == 0.85
        assert "strengths" in result_dict
        assert "weaknesses" in result_dict
        assert "scores" in result_dict
        assert "requirements_met" in result_dict
    
    def test_get_overall_score_positive_metrics_only(self):
        """Test overall score calculation excludes penalties."""
        result = AnalysisResult(
            requirements_met={"test": True},
            scores={
                "task_completion": 80.0,
                "code_quality": 70.0,
                "architecture": 60.0,
                "critical_issues_penalty": 30.0  # Should be excluded
            },
            recommendation=RecommendationLevel.ACCEPT,
            confidence=0.8,
            strengths=["Good code"],
            weaknesses=["Needs work"],
            detailed_feedback="Analysis complete"
        )
        
        # Should only average task_completion, code_quality, architecture
        # (80 + 70 + 60) / 3 = 70, then / 100 = 0.7
        overall_score = result.get_overall_score()
        assert overall_score == pytest.approx(0.7, abs=0.01)
    
    def test_get_overall_score_no_positive_metrics(self):
        """Test overall score with only penalty scores."""
        result = AnalysisResult(
            requirements_met={"test": True},
            scores={
                "critical_issues_penalty": 50.0,
                "violations": 20.0
            },
            recommendation=RecommendationLevel.REJECT,
            confidence=0.5,
            strengths=[],
            weaknesses=["Major issues"],
            detailed_feedback="Failed analysis"
        )
        
        overall_score = result.get_overall_score()
        assert overall_score == 0.0
    
    def test_get_overall_score_empty_scores(self):
        """Test overall score with empty scores."""
        result = AnalysisResult(
            requirements_met={},
            scores={},
            recommendation=RecommendationLevel.REVIEW_REQUIRED,
            confidence=0.5,
            strengths=[],
            weaknesses=[],
            detailed_feedback=""
        )
        
        overall_score = result.get_overall_score()
        assert overall_score == 0.0


@pytest.mark.unit
class TestSubmission:
    """Test Submission entity."""
    
    def test_submission_creation(self):
        """Test basic Submission creation."""
        submission = Submission(
            telegram_user_id="123456789",
            telegram_username="testuser",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND
        )
        
        assert submission.telegram_user_id == "123456789"
        assert submission.telegram_username == "testuser"
        assert submission.github_url == "https://github.com/test/repo"
        assert submission.role == Role.BACKEND
        assert submission.status == SubmissionStatus.PENDING
        assert submission.created_at is not None
        assert submission.updated_at is not None
    
    def test_submission_with_explicit_timestamps(self):
        """Test Submission with explicit timestamps."""
        now = datetime.now(timezone.utc)
        submission = Submission(
            telegram_user_id="123456789",
            telegram_username="testuser",
            github_url="https://github.com/test/repo",
            role=Role.FRONTEND,
            created_at=now,
            updated_at=now
        )
        
        assert submission.created_at == now
        assert submission.updated_at == now
    
    def test_submission_is_complete(self):
        """Test submission completion status checking."""
        # Pending submission
        pending = Submission(
            telegram_user_id="123",
            telegram_username="user",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND,
            status=SubmissionStatus.PENDING
        )
        assert not pending.is_complete()
        
        # Analyzing submission
        analyzing = Submission(
            telegram_user_id="123",
            telegram_username="user", 
            github_url="https://github.com/test/repo",
            role=Role.BACKEND,
            status=SubmissionStatus.ANALYZING
        )
        assert not analyzing.is_complete()
        
        # Completed submission
        completed = Submission(
            telegram_user_id="123",
            telegram_username="user",
            github_url="https://github.com/test/repo", 
            role=Role.BACKEND,
            status=SubmissionStatus.COMPLETED
        )
        assert completed.is_complete()
        
        # Failed submission
        failed = Submission(
            telegram_user_id="123",
            telegram_username="user",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND, 
            status=SubmissionStatus.FAILED
        )
        assert failed.is_complete()
    
    def test_submission_can_retry(self):
        """Test submission retry capability."""
        # Failed submission can be retried
        failed = Submission(
            telegram_user_id="123",
            telegram_username="user",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND,
            status=SubmissionStatus.FAILED
        )
        assert failed.can_retry()
        
        # Completed submission cannot be retried
        completed = Submission(
            telegram_user_id="123", 
            telegram_username="user",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND,
            status=SubmissionStatus.COMPLETED
        )
        assert not completed.can_retry()
        
        # Pending submission cannot be retried
        pending = Submission(
            telegram_user_id="123",
            telegram_username="user",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND,
            status=SubmissionStatus.PENDING
        )
        assert not pending.can_retry()


@pytest.mark.unit
class TestReport:
    """Test Report entity."""
    
    def test_report_creation(self, sample_analysis_result):
        """Test basic Report creation."""
        report = Report(
            submission_id=1,
            analysis_result=sample_analysis_result,
            model_used="test/model",
            tokens_used=1000,
            analysis_duration=30.5
        )
        
        assert report.submission_id == 1
        assert report.analysis_result == sample_analysis_result
        assert report.model_used == "test/model"
        assert report.tokens_used == 1000
        assert report.analysis_duration == 30.5
        assert report.created_at is not None
    
    def test_report_to_dict(self, sample_analysis_result):
        """Test Report dictionary conversion."""
        report = Report(
            id=1,
            submission_id=1,
            analysis_result=sample_analysis_result,
            model_used="test/model",
            tokens_used=1000,
            analysis_duration=30.5
        )
        
        report_dict = report.to_dict()
        
        assert report_dict["id"] == 1
        assert report_dict["submission_id"] == 1
        assert report_dict["model_used"] == "test/model"
        assert report_dict["tokens_used"] == 1000
        assert report_dict["analysis_duration"] == 30.5
        assert "analysis_result" in report_dict
        assert "created_at" in report_dict
    
    def test_report_get_summary(self, sample_analysis_result):
        """Test Report summary generation."""
        report = Report(
            submission_id=1,
            analysis_result=sample_analysis_result,
            model_used="test/model", 
            tokens_used=1000,
            analysis_duration=30.5
        )
        
        summary = report.get_summary()
        
        assert "Accept" in summary  # Recommendation formatted
        assert "85.0%" in summary   # Confidence
        assert "test/model" in summary  # Model used
        assert "30.5s" in summary   # Analysis time


@pytest.mark.unit 
class TestAnalysisRequest:
    """Test AnalysisRequest value object."""
    
    def test_analysis_request_creation(self, sample_repository_content):
        """Test basic AnalysisRequest creation."""
        request = AnalysisRequest(
            repository_content=sample_repository_content,
            role=Role.BACKEND,
            task_requirements="Build a backend service",
            github_url="https://github.com/test/repo"
        )
        
        assert request.repository_content == sample_repository_content
        assert request.role == Role.BACKEND
        assert request.task_requirements == "Build a backend service"
        assert request.github_url == "https://github.com/test/repo"
        assert request.submission_id is None
        assert request.config == {}
    
    def test_analysis_request_with_optional_fields(self, sample_repository_content):
        """Test AnalysisRequest with optional fields."""
        config = {"temperature": 0.2, "max_tokens": 1000}
        request = AnalysisRequest(
            repository_content=sample_repository_content,
            role=Role.FRONTEND,
            task_requirements="Build a frontend app",
            github_url="https://github.com/test/repo",
            submission_id=42,
            config=config
        )
        
        assert request.submission_id == 42
        assert request.config == config


@pytest.mark.unit
class TestEnums:
    """Test enum classes."""
    
    def test_submission_status_values(self):
        """Test SubmissionStatus enum values."""
        assert SubmissionStatus.PENDING.value == "pending"
        assert SubmissionStatus.ANALYZING.value == "analyzing"
        assert SubmissionStatus.COMPLETED.value == "completed"
        assert SubmissionStatus.FAILED.value == "failed"
        assert SubmissionStatus.CANCELLED.value == "cancelled"
    
    def test_role_values(self):
        """Test Role enum values."""
        assert Role.BACKEND.value == "backend"
        assert Role.FRONTEND.value == "frontend"
    
    def test_recommendation_level_values(self):
        """Test RecommendationLevel enum values."""
        assert RecommendationLevel.STRONGLY_REJECT.value == "strongly_reject"
        assert RecommendationLevel.REJECT.value == "reject"
        assert RecommendationLevel.REVIEW_REQUIRED.value == "review_required"
        assert RecommendationLevel.ACCEPT.value == "accept"
        assert RecommendationLevel.STRONGLY_ACCEPT.value == "strongly_accept"


@pytest.mark.unit
class TestModelValidation:
    """Test model validation and edge cases."""
    
    def test_analysis_result_with_minimal_data(self):
        """Test AnalysisResult with minimal required data."""
        result = AnalysisResult(
            requirements_met={},
            scores={},
            recommendation=RecommendationLevel.REVIEW_REQUIRED,
            confidence=0.5,
            strengths=[],
            weaknesses=[],
            detailed_feedback=""
        )
        
        assert result.requirements_met == {}
        assert result.scores == {}
        assert result.strengths == []
        assert result.weaknesses == []
        assert result.suggestions == []  # Default empty list
    
    def test_submission_post_init_behavior(self):
        """Test Submission __post_init__ method."""
        # Test that timestamps are auto-generated
        submission = Submission(
            telegram_user_id="123",
            telegram_username="user",
            github_url="https://github.com/test/repo",
            role=Role.BACKEND
        )
        
        assert submission.created_at is not None
        assert submission.updated_at is not None
        assert isinstance(submission.created_at, datetime)
        assert isinstance(submission.updated_at, datetime)
        
        # Test that explicit timestamps are preserved
        now = datetime.now(timezone.utc)
        explicit_submission = Submission(
            telegram_user_id="123",
            telegram_username="user", 
            github_url="https://github.com/test/repo",
            role=Role.BACKEND,
            created_at=now
        )
        
        assert explicit_submission.created_at == now
    
    def test_report_post_init_behavior(self, sample_analysis_result):
        """Test Report __post_init__ method."""
        # Test that timestamp is auto-generated
        report = Report(
            submission_id=1,
            analysis_result=sample_analysis_result,
            model_used="test/model",
            tokens_used=1000,
            analysis_duration=30.0
        )
        
        assert report.created_at is not None
        assert isinstance(report.created_at, datetime)
        
        # Test that explicit timestamp is preserved
        now = datetime.now(timezone.utc)
        explicit_report = Report(
            submission_id=1,
            analysis_result=sample_analysis_result,
            model_used="test/model",
            tokens_used=1000,
            analysis_duration=30.0,
            created_at=now
        )
        
        assert explicit_report.created_at == now
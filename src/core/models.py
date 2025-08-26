"""
Core domain models for the CV Review System.

This module defines the core business entities and value objects
used throughout the application.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum


class SubmissionStatus(Enum):
    """Status of a code submission."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Role(Enum):
    """Available roles for submissions."""
    BACKEND = "backend"
    FRONTEND = "frontend"


class RecommendationLevel(Enum):
    """Recommendation levels for candidates."""
    STRONGLY_REJECT = "strongly_reject"
    REJECT = "reject"
    REVIEW_REQUIRED = "review_required"
    ACCEPT = "accept"
    STRONGLY_ACCEPT = "strongly_accept"


@dataclass
class FileInfo:
    """
    Information about a single file in a repository.
    
    Attributes:
        path: Relative path of the file in the repository
        content: File content as string
        priority: Priority level (critical, important, useful)
        tokens: Estimated token count for LLM processing
        language: Programming language of the file
    """
    path: str
    content: str
    priority: str = "useful"
    tokens: int = 0
    language: Optional[str] = None
    
    def __repr__(self) -> str:
        """String representation of FileInfo."""
        return f"FileInfo(path={self.path}, priority={self.priority}, tokens={self.tokens})"


@dataclass
class RepositoryContent:
    """
    Processed repository content ready for analysis.
    
    Attributes:
        url: Repository URL
        files: List of processed files
        total_tokens: Total token count across all files
        structure: Repository structure as string
        metadata: Additional repository metadata
    """
    url: str
    files: List[FileInfo]
    total_tokens: int
    structure: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_critical_files(self) -> List[FileInfo]:
        """Get all critical priority files."""
        return [f for f in self.files if f.priority == "critical"]
    
    def get_files_by_language(self, language: str) -> List[FileInfo]:
        """Get all files of a specific language."""
        return [f for f in self.files if f.language == language]


@dataclass
class AnalysisRequest:
    """
    Request for code analysis.
    
    Attributes:
        repository_content: Processed repository content
        role: Role to evaluate against
        task_requirements: Task requirements text
        github_url: GitHub repository URL
        submission_id: Associated submission ID
        config: Additional configuration options
    """
    repository_content: RepositoryContent
    role: Role
    task_requirements: str
    github_url: str
    submission_id: Optional[int] = None
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """
    Result of code analysis.
    
    Attributes:
        requirements_met: Dictionary of requirements and whether they were met
        scores: Dictionary of scoring criteria and scores
        recommendation: Final recommendation level
        confidence: Confidence score (0-1)
        strengths: List of identified strengths
        weaknesses: List of identified weaknesses
        detailed_feedback: Detailed feedback text
        suggestions: List of improvement suggestions
        hiring_decision: Structured hiring decision from LLM (optional)
    """
    requirements_met: Dict[str, bool]
    scores: Dict[str, float]
    recommendation: RecommendationLevel
    confidence: float
    strengths: List[str]
    weaknesses: List[str]
    detailed_feedback: str
    suggestions: List[str] = field(default_factory=list)
    hiring_decision: Optional[Dict[str, str]] = None
    model_used: Optional[str] = None
    penalty_breakdown: Optional[Dict[str, Any]] = None
    architecture_analysis: Optional[Dict[str, Any]] = None
    candidate_explanation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "requirements_met": self.requirements_met,
            "scores": self.scores,
            "recommendation": self.recommendation.value,
            "confidence": self.confidence,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "detailed_feedback": self.detailed_feedback,
            "suggestions": self.suggestions
        }
        if self.hiring_decision:
            result["hiring_decision"] = self.hiring_decision
        if self.model_used:
            result["model_used"] = self.model_used
        if self.penalty_breakdown:
            result["penalty_breakdown"] = self.penalty_breakdown
        if self.architecture_analysis:
            result["architecture_analysis"] = self.architecture_analysis
        if self.candidate_explanation:
            result["candidate_explanation"] = self.candidate_explanation
        return result
    
    def get_overall_score(self) -> float:
        """Calculate overall score from positive metrics only.
        Returns a value between 0 and 1 for percentage formatting.
        Excludes critical_issues_penalty from the average.
        """
        if not self.scores:
            return 0.0
        
        # Exclude penalty-related scores from average
        penalty_keywords = ['penalty', 'critical_issues', 'violations', 'issues']
        positive_scores = []
        
        for key, value in self.scores.items():
            # Skip if this looks like a penalty score
            if any(keyword in key.lower() for keyword in penalty_keywords):
                continue
            positive_scores.append(value)
        
        if not positive_scores:
            # If we can't identify positive scores, try standard keys
            standard_positive = ['task_completion', 'code_quality', 'seniority_indicators', 
                               'functionality', 'architecture', 'documentation']
            for key in standard_positive:
                if key in self.scores:
                    positive_scores.append(self.scores[key])
            
            # Still no scores? Use all non-penalty scores
            if not positive_scores:
                return 0.0
        
        avg_score = sum(positive_scores) / len(positive_scores)
        # Divide by 100 since scores are 0-100 but we want 0-1 for percentage
        return avg_score / 100


@dataclass
class Submission:
    """
    Submission entity representing a candidate's code submission.
    
    Attributes:
        id: Unique identifier
        telegram_user_id: Telegram user ID
        telegram_username: Telegram username
        github_url: Repository URL
        role: Role being applied for
        status: Current status
        created_at: Creation timestamp
        updated_at: Last update timestamp
        completed_at: Completion timestamp
        error_message: Error message if failed
    """
    telegram_user_id: str
    telegram_username: str
    github_url: str
    role: Role
    status: SubmissionStatus = SubmissionStatus.PENDING
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)
    
    def is_complete(self) -> bool:
        """Check if submission is complete."""
        return self.status in [SubmissionStatus.COMPLETED, SubmissionStatus.FAILED]
    
    def can_retry(self) -> bool:
        """Check if submission can be retried."""
        return self.status == SubmissionStatus.FAILED


@dataclass
class Report:
    """
    Analysis report entity containing the results of code analysis.
    
    Attributes:
        id: Unique identifier
        submission_id: Associated submission ID
        analysis_result: Analysis results
        model_used: LLM model used for analysis
        tokens_used: Number of tokens consumed
        analysis_duration: Time taken for analysis in seconds
        created_at: Creation timestamp
    """
    submission_id: int
    analysis_result: AnalysisResult
    model_used: str
    tokens_used: int
    analysis_duration: float
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "submission_id": self.submission_id,
            "analysis_result": self.analysis_result.to_dict(),
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "analysis_duration": self.analysis_duration,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def get_summary(self) -> str:
        """Generate a summary of the report."""
        result = self.analysis_result
        return (
            f"Recommendation: {result.recommendation.value.replace('_', ' ').title()}\n"
            f"Overall Score: {result.get_overall_score():.1%}\n"
            f"Confidence: {result.confidence:.1%}\n"
            f"Model: {self.model_used}\n"
            f"Analysis Time: {self.analysis_duration:.1f}s"
        )
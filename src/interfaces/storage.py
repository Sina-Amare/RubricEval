"""
Storage adapter interface.

This module defines the abstract interface for data storage
(SQLite, PostgreSQL, MongoDB, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from core.models import Submission, Report, SubmissionStatus, Role


class StorageAdapter(ABC):
    """
    Abstract interface for data storage adapters.
    
    Implementations of this interface handle persistent storage
    of submissions, reports, and related data.
    """
    
    # Submission operations
    
    @abstractmethod
    async def create_submission(self, submission: Submission) -> Submission:
        """
        Create a new submission record.
        
        Args:
            submission: Submission to create
            
        Returns:
            Created submission with assigned ID
            
        Raises:
            StorageError: If creation fails
        """
        pass
    
    @abstractmethod
    async def get_submission(self, submission_id: int) -> Optional[Submission]:
        """
        Get submission by ID.
        
        Args:
            submission_id: Submission ID
            
        Returns:
            Submission if found, None otherwise
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    @abstractmethod
    async def find_existing_submission(
        self,
        github_url: str,
        role: str,
        user_id: Optional[str] = None
    ) -> Optional[Submission]:
        """
        Find existing submission by GitHub URL and role.
        
        Args:
            github_url: GitHub repository URL
            role: Role (backend/frontend)
            user_id: Optional user ID to limit search
            
        Returns:
            Most recent matching submission if found, None otherwise
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    @abstractmethod
    async def delete_submission_and_report(self, submission_id: int) -> bool:
        """
        Delete submission and its associated report.
        
        Args:
            submission_id: Submission ID to delete
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            StorageError: If deletion fails
        """
        pass
    
    @abstractmethod
    async def update_submission(
        self,
        submission_id: int,
        status: Optional[SubmissionStatus] = None,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """
        Update submission record.
        
        Args:
            submission_id: Submission ID to update
            status: New status
            error_message: Error message if failed
            completed_at: Completion timestamp
            
        Returns:
            True if updated, False if not found
            
        Raises:
            StorageError: If update fails
        """
        pass
    
    @abstractmethod
    async def get_user_submissions(
        self,
        telegram_user_id: str,
        limit: int = 10
    ) -> List[Submission]:
        """
        Get submissions for a specific user.
        
        Args:
            telegram_user_id: Telegram user ID
            limit: Maximum number of submissions to return
            
        Returns:
            List of user's submissions
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    @abstractmethod
    async def get_pending_submissions(self) -> List[Submission]:
        """
        Get all pending submissions.
        
        Returns:
            List of pending submissions
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    # Report operations
    
    @abstractmethod
    async def create_report(self, report: Report) -> Report:
        """
        Create a new analysis report.
        
        Args:
            report: Report to create
            
        Returns:
            Created report with assigned ID
            
        Raises:
            StorageError: If creation fails
        """
        pass
    
    @abstractmethod
    async def get_report(self, report_id: int) -> Optional[Report]:
        """
        Get report by ID.
        
        Args:
            report_id: Report ID
            
        Returns:
            Report if found, None otherwise
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    @abstractmethod
    async def get_submission_report(self, submission_id: int) -> Optional[Report]:
        """
        Get report for a specific submission.
        
        Args:
            submission_id: Submission ID
            
        Returns:
            Report if found, None otherwise
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    @abstractmethod
    async def get_recent_reports(
        self,
        limit: int = 10,
        role: Optional[Role] = None
    ) -> List[Report]:
        """
        Get recent analysis reports.
        
        Args:
            limit: Maximum number of reports to return
            role: Filter by role if specified
            
        Returns:
            List of recent reports
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    # Statistics operations
    
    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get system statistics.
        
        Returns:
            Dictionary containing:
            - total_submissions: Total number of submissions
            - completed_submissions: Number of completed submissions
            - failed_submissions: Number of failed submissions
            - average_analysis_time: Average analysis duration
            - submissions_by_role: Breakdown by role
            - recommendations_breakdown: Breakdown by recommendation level
            
        Raises:
            StorageError: If query fails
        """
        pass
    
    # Management operations
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize storage (create tables, indexes, etc.).
        
        Raises:
            StorageError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def cleanup_old_data(self, days: int = 30) -> int:
        """
        Clean up old data.
        
        Args:
            days: Delete data older than this many days
            
        Returns:
            Number of records deleted
            
        Raises:
            StorageError: If cleanup fails
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """
        Close storage connections and clean up resources.
        """
        pass
    
    # Optional methods with default implementations
    
    async def check_duplicate_submission(
        self,
        telegram_user_id: str,
        github_url: str,
        hours: int = 24
    ) -> bool:
        """
        Check if user has already submitted this repository recently.
        
        Args:
            telegram_user_id: Telegram user ID
            github_url: Repository URL
            hours: Time window to check (default 24 hours)
            
        Returns:
            True if duplicate exists, False otherwise
        """
        return False
    
    async def backup(self, backup_path: str) -> bool:
        """
        Create backup of storage data.
        
        Args:
            backup_path: Path to save backup
            
        Returns:
            True if backup successful, False otherwise
        """
        return False
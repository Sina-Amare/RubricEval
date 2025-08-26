"""
SQLite storage adapter implementation.

This module provides SQLite storage implementation using SQLAlchemy.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from functools import partial

from sqlalchemy import create_engine, and_, desc, func
from sqlalchemy.orm import sessionmaker, Session as SessionType
from sqlalchemy.exc import SQLAlchemyError

from interfaces.storage import StorageAdapter
from core.models import (
    Submission as DomainSubmission,
    Report as DomainReport,
    SubmissionStatus,
    Role,
    AnalysisResult,
    RecommendationLevel
)
from core.exceptions import StorageError
from database import (
    Base,
    Submission as DBSubmission,
    Report as DBReport,
    engine as db_engine,
    Session as SessionFactory
)
from utils.logger import setup_logger, log_error_with_context

# Initialize logger
logger = setup_logger(__name__)

# Thread pool for database operations
executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="sqlite_adapter")


class SQLiteAdapter(StorageAdapter):
    """
    SQLite storage adapter using SQLAlchemy.
    
    This adapter provides async wrappers around SQLAlchemy operations
    using ThreadPoolExecutor to avoid blocking the event loop.
    """
    
    def __init__(self, database_url: str = None):
        """
        Initialize SQLite adapter.
        
        Args:
            database_url: Optional database URL. Uses config default if not provided.
        """
        if database_url:
            self.engine = create_engine(database_url)
            self.SessionFactory = sessionmaker(bind=self.engine)
        else:
            # Use existing configured engine and session factory
            self.engine = db_engine
            self.SessionFactory = SessionFactory
        
        logger.info("SQLite adapter initialized")
    
    # Submission operations
    
    async def create_submission(self, submission: DomainSubmission) -> DomainSubmission:
        """
        Create a new submission record.
        
        Args:
            submission: Domain submission model
            
        Returns:
            Created submission with assigned ID
            
        Raises:
            StorageError: If creation fails
        """
        try:
            def _create():
                session = self.SessionFactory()
                try:
                    # Convert domain model to database model
                    db_submission = DBSubmission(
                        telegram_user_id=submission.telegram_user_id,
                        telegram_username=submission.telegram_username,
                        github_url=submission.github_url,
                        role=submission.role.value,
                        status=submission.status.value,
                        created_at=submission.created_at or datetime.now(timezone.utc)
                    )
                    
                    session.add(db_submission)
                    session.commit()
                    session.refresh(db_submission)
                    
                    # Convert back to domain model
                    return self._db_to_domain_submission(db_submission)
                    
                finally:
                    session.close()
            
            result = await asyncio.get_event_loop().run_in_executor(executor, _create)
            logger.info(f"Created submission {result.id} for user {result.telegram_user_id}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to create submission: {str(e)}"
            logger.error(error_msg)
            log_error_with_context(logger, e, {'user_id': submission.telegram_user_id})
            raise StorageError(error_msg, details={'submission': submission})
    
    async def get_submission(self, submission_id: int) -> Optional[DomainSubmission]:
        """
        Get submission by ID.
        
        Args:
            submission_id: Submission ID
            
        Returns:
            Submission if found, None otherwise
            
        Raises:
            StorageError: If query fails
        """
        try:
            def _get():
                session = self.SessionFactory()
                try:
                    db_submission = session.query(DBSubmission).filter_by(id=submission_id).first()
                    if db_submission:
                        return self._db_to_domain_submission(db_submission)
                    return None
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _get)
            
        except Exception as e:
            error_msg = f"Failed to get submission {submission_id}: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    async def find_existing_submission(
        self,
        github_url: str,
        role: str,
        user_id: Optional[str] = None
    ) -> Optional[DomainSubmission]:
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
        try:
            def _find():
                session = self.SessionFactory()
                try:
                    query = session.query(DBSubmission).filter(
                        DBSubmission.github_url == github_url,
                        DBSubmission.role == role
                    )
                    
                    if user_id:
                        query = query.filter(DBSubmission.telegram_user_id == user_id)
                    
                    # Get the most recent submission
                    db_submission = query.order_by(DBSubmission.created_at.desc()).first()
                    
                    if db_submission:
                        return self._db_to_domain_submission(db_submission)
                    return None
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _find)
            
        except Exception as e:
            error_msg = f"Failed to find existing submission: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
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
        try:
            def _delete():
                session = self.SessionFactory()
                try:
                    # First delete any associated reports
                    report_count = session.query(DBReport).filter_by(submission_id=submission_id).delete()
                    
                    # Then delete the submission
                    submission_count = session.query(DBSubmission).filter_by(id=submission_id).delete()
                    
                    if submission_count > 0:
                        session.commit()
                        logger.info(f"Deleted submission {submission_id} and {report_count} associated reports")
                        return True
                    return False
                    
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _delete)
            
        except Exception as e:
            error_msg = f"Failed to delete submission {submission_id}: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
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
        try:
            def _update():
                session = self.SessionFactory()
                try:
                    db_submission = session.query(DBSubmission).filter_by(id=submission_id).first()
                    if not db_submission:
                        return False
                    
                    if status is not None:
                        db_submission.status = status.value
                    if error_message is not None:
                        db_submission.error_message = error_message
                    if completed_at is not None:
                        db_submission.completed_at = completed_at
                    
                    session.commit()
                    return True
                    
                finally:
                    session.close()
            
            result = await asyncio.get_event_loop().run_in_executor(executor, _update)
            if result:
                logger.info(f"Updated submission {submission_id}: status={status}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to update submission {submission_id}: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    async def get_user_submissions(
        self,
        telegram_user_id: str,
        limit: int = 10
    ) -> List[DomainSubmission]:
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
        try:
            def _get_user_submissions():
                session = self.SessionFactory()
                try:
                    db_submissions = session.query(DBSubmission)\
                        .filter_by(telegram_user_id=telegram_user_id)\
                        .order_by(desc(DBSubmission.created_at))\
                        .limit(limit)\
                        .all()
                    
                    return [self._db_to_domain_submission(s) for s in db_submissions]
                    
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _get_user_submissions)
            
        except Exception as e:
            error_msg = f"Failed to get submissions for user {telegram_user_id}: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    async def get_pending_submissions(self) -> List[DomainSubmission]:
        """
        Get all pending submissions.
        
        Returns:
            List of pending submissions
            
        Raises:
            StorageError: If query fails
        """
        try:
            def _get_pending():
                session = self.SessionFactory()
                try:
                    db_submissions = session.query(DBSubmission)\
                        .filter_by(status='pending')\
                        .order_by(DBSubmission.created_at)\
                        .all()
                    
                    return [self._db_to_domain_submission(s) for s in db_submissions]
                    
                finally:
                    session.close()
            
            result = await asyncio.get_event_loop().run_in_executor(executor, _get_pending)
            logger.debug(f"Found {len(result)} pending submissions")
            return result
            
        except Exception as e:
            error_msg = f"Failed to get pending submissions: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    # Report operations
    
    async def create_report(self, report: DomainReport) -> DomainReport:
        """
        Create a new analysis report.
        
        Args:
            report: Domain report model
            
        Returns:
            Created report with assigned ID
            
        Raises:
            StorageError: If creation fails
        """
        try:
            def _create():
                session = self.SessionFactory()
                try:
                    # Convert analysis result to JSON
                    analysis_dict = report.analysis_result.to_dict()
                    # Add extra metadata to the analysis dict
                    analysis_dict['model_used'] = report.model_used
                    analysis_dict['tokens_used'] = report.tokens_used
                    analysis_dict['analysis_duration'] = report.analysis_duration
                    
                    analysis_json = json.dumps(analysis_dict)
                    
                    # Extract individual scores
                    scores = report.analysis_result.scores
                    
                    # Map LLM recommendation to database format
                    # LLM can return various formats, normalize them
                    llm_rec = str(analysis_dict.get('recommendation', 'maybe')).lower().strip()
                    
                    if llm_rec in ['strong_yes', 'strongly_accept']:
                        db_recommendation = 'STRONGLY_ACCEPT'
                    elif llm_rec in ['yes', 'accept']:
                        db_recommendation = 'ACCEPT'
                    elif llm_rec in ['maybe', 'review_required', 'review']:
                        db_recommendation = 'REVIEW_REQUIRED'
                    elif llm_rec in ['no', 'reject']:
                        db_recommendation = 'REJECT'
                    elif llm_rec in ['strong_no', 'strongly_reject']:
                        db_recommendation = 'STRONGLY_REJECT'
                    else:
                        # Fallback based on scores if recommendation is unexpected
                        scores = report.analysis_result.scores
                        
                        # Calculate average of positive metrics only
                        positive_keys = ['task_completion', 'code_quality', 'seniority_indicators']
                        positive_scores = [scores.get(k, 0) for k in positive_keys if k in scores]
                        avg_score = sum(positive_scores) / len(positive_scores) if positive_scores else 0
                        
                        # Check critical issues
                        penalty = scores.get('critical_issues_penalty', 0)
                        
                        if penalty >= 50:
                            logger.warning(f"Unknown recommendation '{llm_rec}', using REJECT due to critical issues (penalty: {penalty})")
                            db_recommendation = 'REJECT'
                        elif avg_score >= 70:
                            logger.warning(f"Unknown recommendation '{llm_rec}', using ACCEPT (score: {avg_score:.1f}%)")
                            db_recommendation = 'ACCEPT'
                        else:
                            logger.warning(f"Unknown recommendation '{llm_rec}', using REJECT (score: {avg_score:.1f}%)")
                            db_recommendation = 'REJECT'
                    
                    # Create database report
                    db_report = DBReport(
                        submission_id=report.submission_id,
                        analysis_result=analysis_json,  # Full analysis as JSON
                        recommendation=db_recommendation,
                        confidence=report.analysis_result.confidence,
                        completeness_score=scores.get('completeness', 0),
                        quality_score=scores.get('quality', 0),
                        architecture_score=scores.get('architecture', 0),
                        testing_score=scores.get('testing', 0),
                        created_at=report.created_at or datetime.now(timezone.utc)
                    )
                    
                    session.add(db_report)
                    session.commit()
                    session.refresh(db_report)
                    
                    # Convert back to domain model
                    return self._db_to_domain_report(db_report)
                    
                finally:
                    session.close()
            
            result = await asyncio.get_event_loop().run_in_executor(executor, _create)
            logger.info(f"Created report {result.id} for submission {result.submission_id}")
            return result
            
        except Exception as e:
            error_msg = f"Failed to create report: {str(e)}"
            logger.error(error_msg)
            log_error_with_context(logger, e, {'submission_id': report.submission_id})
            raise StorageError(error_msg)
    
    async def get_report(self, report_id: int) -> Optional[DomainReport]:
        """
        Get report by ID.
        
        Args:
            report_id: Report ID
            
        Returns:
            Report if found, None otherwise
            
        Raises:
            StorageError: If query fails
        """
        try:
            def _get():
                session = self.SessionFactory()
                try:
                    db_report = session.query(DBReport).filter_by(id=report_id).first()
                    if db_report:
                        return self._db_to_domain_report(db_report)
                    return None
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _get)
            
        except Exception as e:
            error_msg = f"Failed to get report {report_id}: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    async def get_submission_report(self, submission_id: int) -> Optional[DomainReport]:
        """
        Get report for a specific submission.
        
        Args:
            submission_id: Submission ID
            
        Returns:
            Report if found, None otherwise
            
        Raises:
            StorageError: If query fails
        """
        try:
            def _get():
                session = self.SessionFactory()
                try:
                    db_report = session.query(DBReport).filter_by(submission_id=submission_id).first()
                    if db_report:
                        return self._db_to_domain_report(db_report)
                    return None
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _get)
            
        except Exception as e:
            error_msg = f"Failed to get report for submission {submission_id}: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    async def get_all_reports(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        role: Optional[Role] = None
    ) -> List[DomainReport]:
        """
        Get all reports with optional pagination and role filtering.
        
        Args:
            limit: Maximum number of reports to return (None for all)
            offset: Number of reports to skip (for pagination)
            role: Optional role filter
            
        Returns:
            List of reports
            
        Raises:
            StorageError: If query fails
        """
        try:
            def _get_all():
                session = self.SessionFactory()
                try:
                    query = session.query(DBReport).join(
                        DBSubmission, DBReport.submission_id == DBSubmission.id
                    )
                    
                    # Apply role filter if specified
                    if role:
                        query = query.filter(DBSubmission.role == role.value)
                    
                    # Order by creation date (newest first)
                    query = query.order_by(DBReport.created_at.desc())
                    
                    # Apply pagination
                    if offset:
                        query = query.offset(offset)
                    if limit:
                        query = query.limit(limit)
                    
                    db_reports = query.all()
                    return [self._db_to_domain_report(r) for r in db_reports]
                    
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _get_all)
            
        except Exception as e:
            error_msg = f"Failed to get all reports: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    async def get_reports_by_role(
        self,
        role: Role,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[DomainReport]:
        """
        Get reports filtered by role.
        
        Args:
            role: Role to filter by
            limit: Maximum number of reports to return
            offset: Number of reports to skip
            
        Returns:
            List of reports for the specified role
            
        Raises:
            StorageError: If query fails
        """
        return await self.get_all_reports(limit=limit, offset=offset, role=role)
    
    async def get_recent_reports(
        self,
        limit: int = 10,
        role: Optional[Role] = None
    ) -> List[DomainReport]:
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
        try:
            def _get_recent():
                session = self.SessionFactory()
                try:
                    query = session.query(DBReport).join(DBSubmission)
                    
                    if role:
                        query = query.filter(DBSubmission.role == role.value)
                    
                    db_reports = query.order_by(desc(DBReport.created_at))\
                        .limit(limit)\
                        .all()
                    
                    return [self._db_to_domain_report(r) for r in db_reports]
                    
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _get_recent)
            
        except Exception as e:
            error_msg = f"Failed to get recent reports: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    # Statistics operations
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get system statistics.
        
        Returns:
            Dictionary containing system statistics
            
        Raises:
            StorageError: If query fails
        """
        try:
            def _get_stats():
                session = self.SessionFactory()
                try:
                    # Total submissions
                    total_submissions = session.query(func.count(DBSubmission.id)).scalar()
                    
                    # Status breakdown
                    status_counts = session.query(
                        DBSubmission.status,
                        func.count(DBSubmission.id)
                    ).group_by(DBSubmission.status).all()
                    
                    # Role breakdown
                    role_counts = session.query(
                        DBSubmission.role,
                        func.count(DBSubmission.id)
                    ).group_by(DBSubmission.role).all()
                    
                    # Recommendation breakdown
                    recommendation_counts = session.query(
                        DBReport.recommendation,
                        func.count(DBReport.id)
                    ).group_by(DBReport.recommendation).all()
                    
                    # Average confidence score (since we don't have analysis_duration in DB)
                    avg_confidence = session.query(func.avg(DBReport.confidence)).scalar()
                    
                    # Recent activity (last 24 hours)
                    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
                    recent_submissions = session.query(func.count(DBSubmission.id))\
                        .filter(DBSubmission.created_at >= yesterday).scalar()
                    
                    return {
                        'total_submissions': total_submissions or 0,
                        'status_breakdown': dict(status_counts),
                        'role_breakdown': dict(role_counts),
                        'recommendation_breakdown': dict(recommendation_counts),
                        'average_analysis_time': 0,  # Not tracked in current DB schema
                        'average_confidence': avg_confidence or 0,
                        'recent_submissions_24h': recent_submissions or 0,
                        'completed_submissions': dict(status_counts).get('completed', 0),
                        'failed_submissions': dict(status_counts).get('failed', 0)
                    }
                    
                finally:
                    session.close()
            
            stats = await asyncio.get_event_loop().run_in_executor(executor, _get_stats)
            logger.debug(f"Generated statistics: {stats['total_submissions']} total submissions")
            return stats
            
        except Exception as e:
            error_msg = f"Failed to get statistics: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    # Management operations
    
    async def initialize(self) -> None:
        """
        Initialize storage (create tables, indexes, etc.).
        
        Raises:
            StorageError: If initialization fails
        """
        try:
            def _init():
                Base.metadata.create_all(bind=self.engine)
                logger.info("Database tables created/verified")
            
            await asyncio.get_event_loop().run_in_executor(executor, _init)
            
        except Exception as e:
            error_msg = f"Failed to initialize database: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
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
        try:
            def _cleanup():
                session = self.SessionFactory()
                try:
                    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
                    
                    # First get IDs of old submissions
                    old_submission_ids = session.query(DBSubmission.id)\
                        .filter(DBSubmission.created_at < cutoff_date).all()
                    old_submission_ids = [id[0] for id in old_submission_ids]
                    
                    total_deleted = 0
                    
                    if old_submission_ids:
                        # Delete old reports first (foreign key constraint)
                        report_count = session.query(DBReport)\
                            .filter(DBReport.submission_id.in_(old_submission_ids))\
                            .delete(synchronize_session=False)
                        
                        # Then delete old submissions
                        submission_count = session.query(DBSubmission)\
                            .filter(DBSubmission.id.in_(old_submission_ids))\
                            .delete(synchronize_session=False)
                        
                        session.commit()
                        
                        total_deleted = report_count + submission_count
                        logger.info(f"Cleaned up {total_deleted} old records ({submission_count} submissions, {report_count} reports)")
                    
                    return total_deleted
                    
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _cleanup)
            
        except Exception as e:
            error_msg = f"Failed to cleanup old data: {str(e)}"
            logger.error(error_msg)
            raise StorageError(error_msg)
    
    async def close(self) -> None:
        """
        Close storage connections and clean up resources.
        """
        try:
            # Close the engine connection pool
            self.engine.dispose()
            logger.info("SQLite adapter closed")
        except Exception as e:
            logger.error(f"Error closing SQLite adapter: {e}")
    
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
        try:
            def _check_duplicate():
                session = self.SessionFactory()
                try:
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                    
                    duplicate = session.query(DBSubmission).filter(
                        and_(
                            DBSubmission.telegram_user_id == telegram_user_id,
                            DBSubmission.github_url == github_url,
                            DBSubmission.created_at >= cutoff_time
                        )
                    ).first()
                    
                    return duplicate is not None
                    
                finally:
                    session.close()
            
            return await asyncio.get_event_loop().run_in_executor(executor, _check_duplicate)
            
        except Exception as e:
            logger.warning(f"Error checking duplicate submission: {e}")
            return False  # Don't block submission on error
    
    # Private helper methods
    
    def _db_to_domain_submission(self, db_submission: DBSubmission) -> DomainSubmission:
        """Convert database submission to domain model."""
        return DomainSubmission(
            id=db_submission.id,
            telegram_user_id=db_submission.telegram_user_id,
            telegram_username=db_submission.telegram_username,
            github_url=db_submission.github_url,
            role=Role(db_submission.role),
            status=SubmissionStatus(db_submission.status),
            created_at=db_submission.created_at,
            updated_at=db_submission.created_at,  # Using created_at as we don't track updates
            completed_at=db_submission.completed_at,
            error_message=db_submission.error_message
        )
    
    def _db_to_domain_report(self, db_report: DBReport) -> DomainReport:
        """Convert database report to domain model."""
        # Parse the JSON stored in analysis_result field
        if db_report.analysis_result:
            analysis_dict = json.loads(db_report.analysis_result)
            
            # Map database recommendation back to enum
            # Unified mapping that handles all possible formats
            llm_rec = analysis_dict.get('recommendation', '').lower()  # This is what LLM returned
            db_rec = (db_report.recommendation or '').lower()  # This is what's stored in DB
            
            # Try LLM recommendation first, then DB recommendation
            rec_to_check = llm_rec if llm_rec else db_rec
            
            # Comprehensive mapping of all possible values
            if rec_to_check in ['strong_yes', 'strongly_accept', 'strong yes']:
                recommendation = RecommendationLevel.STRONGLY_ACCEPT
            elif rec_to_check in ['yes', 'accept']:
                recommendation = RecommendationLevel.ACCEPT
            elif rec_to_check in ['no', 'reject']:
                recommendation = RecommendationLevel.REJECT
            elif rec_to_check in ['strong_no', 'strongly_reject', 'strong no']:
                recommendation = RecommendationLevel.STRONGLY_REJECT
            elif rec_to_check in ['maybe', 'review_required', 'review required', 'review']:
                recommendation = RecommendationLevel.REVIEW_REQUIRED
            else:
                # Default based on scores if recommendation is unrecognized
                scores = analysis_dict.get('scores', {})
                
                # Calculate average of positive metrics only
                positive_keys = ['task_completion', 'code_quality', 'seniority_indicators']
                positive_scores = [scores.get(k, 0) for k in positive_keys if k in scores]
                avg_score = sum(positive_scores) / len(positive_scores) if positive_scores else 0
                
                # Check critical issues
                penalty = scores.get('critical_issues_penalty', 0)
                
                if penalty >= 50:
                    logger.warning(f"Unknown recommendation '{rec_to_check}', using REJECT due to critical issues (penalty: {penalty})")
                    recommendation = RecommendationLevel.REJECT
                elif avg_score >= 70:
                    logger.warning(f"Unknown recommendation '{rec_to_check}', using ACCEPT (score: {avg_score})")
                    recommendation = RecommendationLevel.ACCEPT
                else:
                    logger.warning(f"Unknown recommendation '{rec_to_check}', using REJECT (score: {avg_score})")
                    recommendation = RecommendationLevel.REJECT
            
            # Reconstruct scores from individual fields or from dict
            if 'scores' in analysis_dict:
                scores = analysis_dict['scores']
            else:
                # Fallback to individual score fields
                scores = {
                    'completeness': db_report.completeness_score or 0,
                    'quality': db_report.quality_score or 0,
                    'architecture': db_report.architecture_score or 0,
                    'testing': db_report.testing_score or 0
                }
            
            analysis_result = AnalysisResult(
                requirements_met=analysis_dict.get('requirements_met', {}),
                scores=scores,
                recommendation=recommendation,
                confidence=analysis_dict.get('confidence', db_report.confidence or 0),
                strengths=analysis_dict.get('strengths', []),
                weaknesses=analysis_dict.get('weaknesses', []),
                detailed_feedback=analysis_dict.get('detailed_feedback', ''),
                suggestions=analysis_dict.get('suggestions', []),
                hiring_decision=analysis_dict.get('hiring_decision'),
                model_used=analysis_dict.get('model_used'),
                penalty_breakdown=analysis_dict.get('penalty_breakdown'),
                architecture_analysis=analysis_dict.get('architecture_analysis')
            )
            
            # Extract metadata from analysis dict
            model_used = analysis_dict.get('model_used', '')
            tokens_used = analysis_dict.get('tokens_used', 0)
            analysis_duration = analysis_dict.get('analysis_duration', 0)
        else:
            # Fallback for empty analysis
            analysis_result = AnalysisResult(
                requirements_met={},
                scores={
                    'completeness': db_report.completeness_score or 0,
                    'quality': db_report.quality_score or 0,
                    'architecture': db_report.architecture_score or 0,
                    'testing': db_report.testing_score or 0
                },
                recommendation=RecommendationLevel.REVIEW_REQUIRED,
                confidence=db_report.confidence or 0,
                strengths=[],
                weaknesses=[],
                detailed_feedback='',
                suggestions=[],
                hiring_decision=None,
                model_used=None,
                penalty_breakdown=None,
                architecture_analysis=None
            )
            model_used = ''
            tokens_used = 0
            analysis_duration = 0
        
        return DomainReport(
            id=db_report.id,
            submission_id=db_report.submission_id,
            analysis_result=analysis_result,
            model_used=model_used,
            tokens_used=tokens_used,
            analysis_duration=analysis_duration,
            created_at=db_report.created_at
        )
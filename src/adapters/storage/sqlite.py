"""
SQLite storage adapter implementation.

This module provides SQLite storage implementation using SQLAlchemy.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
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
                        created_at=submission.created_at or datetime.utcnow()
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
                    
                    # Create database report
                    db_report = DBReport(
                        submission_id=report.submission_id,
                        analysis_result=analysis_json,  # Full analysis as JSON
                        recommendation=report.analysis_result.recommendation.value.upper()
                        if 'accept' in report.analysis_result.recommendation.value.lower()
                        else 'REJECT',
                        confidence=report.analysis_result.confidence,
                        completeness_score=scores.get('completeness', 0),
                        quality_score=scores.get('quality', 0),
                        architecture_score=scores.get('architecture', 0),
                        testing_score=scores.get('testing', 0),
                        created_at=report.created_at or datetime.utcnow()
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
                    yesterday = datetime.utcnow() - timedelta(days=1)
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
                    cutoff_date = datetime.utcnow() - timedelta(days=days)
                    
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
                    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                    
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
            
            # Convert recommendation string back to enum
            recommendation_str = analysis_dict.get('recommendation', db_report.recommendation or 'review_required')
            try:
                recommendation = RecommendationLevel(recommendation_str)
            except ValueError:
                # Handle old format or invalid values
                if 'ACCEPT' in str(recommendation_str).upper():
                    recommendation = RecommendationLevel.ACCEPT
                elif 'REJECT' in str(recommendation_str).upper():
                    recommendation = RecommendationLevel.REJECT
                else:
                    recommendation = RecommendationLevel.REVIEW_REQUIRED
            
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
                suggestions=analysis_dict.get('suggestions', [])
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
                detailed_feedback=''
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
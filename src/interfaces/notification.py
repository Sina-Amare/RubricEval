"""
Notification adapter interface.

This module defines the abstract interface for notification systems
(Telegram, Email, Webhook, etc.).
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from core.models import Submission, Report, AnalysisResult


class NotificationAdapter(ABC):
    """
    Abstract interface for notification adapters.
    
    Implementations of this interface handle sending notifications
    to users through various channels.
    """
    
    @abstractmethod
    async def send_welcome_message(self, user_id: str, username: str) -> bool:
        """
        Send welcome message to new user.
        
        Args:
            user_id: User identifier
            username: User display name
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_submission_received(
        self,
        user_id: str,
        submission: Submission
    ) -> bool:
        """
        Notify user that submission was received.
        
        Args:
            user_id: User identifier
            submission: Submission details
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_analysis_started(
        self,
        user_id: str,
        submission: Submission
    ) -> bool:
        """
        Notify user that analysis has started.
        
        Args:
            user_id: User identifier
            submission: Submission details
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_analysis_complete(
        self,
        user_id: str,
        submission: Submission,
        report: Report
    ) -> bool:
        """
        Send analysis results to user.
        
        Args:
            user_id: User identifier
            submission: Submission details
            report: Analysis report
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_analysis_failed(
        self,
        user_id: str,
        submission: Submission,
        error_message: str
    ) -> bool:
        """
        Notify user that analysis failed.
        
        Args:
            user_id: User identifier
            submission: Submission details
            error_message: Error description
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_error_message(
        self,
        user_id: str,
        error_message: str
    ) -> bool:
        """
        Send error message to user.
        
        Args:
            user_id: User identifier
            error_message: Error description
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def request_role_selection(
        self,
        user_id: str,
        repository_url: str
    ) -> bool:
        """
        Request user to select a role for evaluation.
        
        Args:
            user_id: User identifier
            repository_url: Repository being submitted
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_manager_report(
        self,
        manager_id: str,
        reports: List[Report],
        statistics: Dict[str, Any]
    ) -> bool:
        """
        Send reports summary to manager.
        
        Args:
            manager_id: Manager identifier
            reports: List of recent reports
            statistics: System statistics
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    # Optional methods with default implementations
    
    async def send_rate_limit_warning(
        self,
        user_id: str,
        retry_after: int
    ) -> bool:
        """
        Notify user about rate limiting.
        
        Args:
            user_id: User identifier
            retry_after: Seconds to wait before retry
            
        Returns:
            True if sent successfully, False otherwise
        """
        return await self.send_error_message(
            user_id,
            f"Rate limit exceeded. Please try again in {retry_after} seconds."
        )
    
    async def send_maintenance_notice(
        self,
        user_ids: List[str],
        message: str
    ) -> Dict[str, bool]:
        """
        Send maintenance notice to multiple users.
        
        Args:
            user_ids: List of user identifiers
            message: Maintenance message
            
        Returns:
            Dictionary mapping user_id to success status
        """
        results = {}
        for user_id in user_ids:
            results[user_id] = await self.send_error_message(user_id, message)
        return results
    
    def format_report_summary(self, report: Report) -> str:
        """
        Format report summary for display.
        
        Args:
            report: Analysis report
            
        Returns:
            Formatted summary string
        """
        result = report.analysis_result
        summary = f"""
📊 **Analysis Results**

**Recommendation:** {result.recommendation.value.replace('_', ' ').title()}
**Confidence:** {result.confidence:.1%}
**Overall Score:** {result.get_overall_score():.1%}

**Strengths:**
{chr(10).join(f'✅ {s}' for s in result.strengths[:3])}

**Areas for Improvement:**
{chr(10).join(f'⚠️ {w}' for w in result.weaknesses[:3])}

**Model Used:** {report.model_used}
**Analysis Time:** {report.analysis_duration:.1f}s
        """
        return summary.strip()
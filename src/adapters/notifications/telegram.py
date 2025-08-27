"""
Telegram notification adapter implementation.

This module provides Telegram bot functionality for the CV Review system.
Manager-only bot for analyzing candidate GitHub repositories.
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

# Apply network fixes BEFORE importing telegram
from utils.network_fix import install_network_fixes
install_network_fixes()
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    Bot
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.error import TelegramError, TimedOut, NetworkError
from telegram.constants import ChatAction, ParseMode

from interfaces.notification import NotificationAdapter
from core.models import Submission, Report, AnalysisResult
from core.exceptions import NotificationError
from utils.logger import setup_logger, log_error_with_context
from utils.prompts import escape_markdown
from config import BOT_TOKEN, MANAGER_IDS

# Initialize logger
logger = setup_logger(__name__)

# Conversation states
WAITING_FOR_URL = 1
WAITING_FOR_ROLE = 2

# Message templates
WELCOME_MESSAGE = """
👋 Welcome to CV Review Bot!

I help you analyze candidate GitHub repositories quickly and consistently.

How to use:
1. Type /analyze
2. Send me the GitHub repository URL
3. Select the position (Backend/Frontend)
4. Get detailed analysis in 2-5 minutes

Commands:
/analyze - Start new analysis
/recent - View recent analyses
/stats - View statistics
/help - Show this message
"""

URL_PROMPT = """
📝 Please send me the GitHub repository URL for analysis.

Example formats:
• https://github.com/username/repository
• https://github.com/username/repo.git
"""

INVALID_URL_MESSAGE = """
❌ That doesn't appear to be a valid GitHub URL.

Please check the URL format:
✓ https://github.com/username/repo
✓ https://github.com/username/repo.git

Try again:
"""

REPO_ERROR_MESSAGE = """
⚠️ I couldn't access this repository. Please check:
• Is the repository public?
• Is the URL correct?
• Does the repository exist?

Please send the URL again or type /cancel to stop.
"""


class TelegramAdapter(NotificationAdapter):
    """
    Telegram notification adapter for manager-only bot.
    
    This adapter handles all Telegram bot interactions for the CV Review system.
    """
    
    def __init__(self, bot_token: str = None):
        """
        Initialize Telegram adapter.
        
        Args:
            bot_token: Optional bot token. Uses config default if not provided.
        """
        self.bot_token = bot_token or BOT_TOKEN
        self.application = None
        self.bot = None
        
        # Store for ongoing conversations
        self.user_sessions = {}
        
        logger.info("Telegram adapter initialized")
    
    async def initialize(self):
        """Initialize the Telegram bot application."""
        try:
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            self.bot = self.application.bot
            
            # Test bot connection
            bot_info = await self.bot.get_me()
            logger.info(f"Bot initialized: @{bot_info.username}")
            
            return True
        except Exception as e:
            error_msg = f"Failed to initialize Telegram bot: {str(e)}"
            logger.error(error_msg)
            raise NotificationError(error_msg)
    
    # Manager command implementations (simplified for manager-only use)
    
    async def send_welcome_message(self, user_id: str, username: str) -> bool:
        """
        Send welcome message.
        
        Args:
            user_id: Telegram user ID
            username: User display name
            
        Returns:
            True if sent successfully
        """
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=WELCOME_MESSAGE,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"Welcome message sent to {username} ({user_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")
            return False
    
    async def send_submission_received(
        self,
        user_id: str,
        submission: Submission
    ) -> bool:
        """
        Notify that submission was received.
        
        Args:
            user_id: User identifier
            submission: Submission details
            
        Returns:
            True if sent successfully
        """
        try:
            # Extract repo name from URL
            repo_name = submission.github_url.split('/')[-1].replace('.git', '')
            
            message = f"""
✅ Repository received!

📁 Repository: `{repo_name}`
💼 Position: {submission.role.value}
🔄 Status: Starting analysis...

I'll notify you when the analysis is complete.
This typically takes 2-5 minutes.
            """
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send submission received: {e}")
            return False
    
    async def send_analysis_started(
        self,
        user_id: str,
        submission: Submission
    ) -> bool:
        """
        Notify that analysis has started.
        
        Args:
            user_id: User identifier
            submission: Submission details
            
        Returns:
            True if sent successfully
        """
        try:
            message = "🔄 Analysis in progress..."
            
            # Send typing action to show bot is working
            await self.bot.send_chat_action(
                chat_id=user_id,
                action=ChatAction.TYPING
            )
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send analysis started: {e}")
            return False
    
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
            True if sent successfully
        """
        try:
            # Format the detailed report (already in HTML format)
            report_text = self._format_analysis_report(submission, report)
            
            # Split if too long (Telegram limit is 4096 characters)
            if len(report_text) > 4000:
                # Send summary first
                summary = self._format_report_summary(submission, report)
                await self.bot.send_message(
                    chat_id=user_id,
                    text=summary,
                    parse_mode=ParseMode.HTML
                )
                
                # Send detailed parts
                parts = self._split_long_message(report_text)
                for part in parts:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=part,
                        parse_mode=ParseMode.HTML
                    )
            else:
                # Send the report directly (it's already in HTML format)
                await self.bot.send_message(
                    chat_id=user_id,
                    text=report_text,
                    parse_mode=ParseMode.HTML
                )
            
            logger.info(f"Analysis report sent for submission {submission.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send analysis complete: {e}")
            return False
    
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
            True if sent successfully
        """
        try:
            # Make error message user-friendly
            if "token" in error_message.lower():
                user_error = "The repository is too large to analyze (exceeds token limit)."
            elif "timeout" in error_message.lower():
                user_error = "The analysis timed out. The repository might be too complex."
            elif "rate limit" in error_message.lower():
                user_error = "API rate limit reached. Please try again in a few minutes."
            else:
                user_error = "An error occurred during analysis."
            
            message = f"""
❌ Analysis Failed

{user_error}

Original error: `{error_message[:200]}`

You can:
• Try again with /analyze
• Check if the repository is public
• Ensure the repository has code files
            """
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send analysis failed: {e}")
            return False
    
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
            True if sent successfully
        """
        try:
            message = f"⚠️ {error_message}"
            await self.bot.send_message(
                chat_id=user_id,
                text=message
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
            return False
    
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
            True if sent successfully
        """
        try:
            # Extract repo name for display
            repo_name = repository_url.split('/')[-1].replace('.git', '')
            
            message = f"""
✅ Repository found: `{repo_name}`

Which position is this candidate applying for?
            """
            
            # Create inline keyboard for role selection
            keyboard = [
                [
                    InlineKeyboardButton("👨‍💻 Backend Developer", callback_data="role_backend"),
                    InlineKeyboardButton("🎨 Frontend Developer", callback_data="role_frontend")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to request role selection: {e}")
            return False
    
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
            True if sent successfully
        """
        try:
            # Format statistics
            stats_text = f"""
📊 System Statistics
━━━━━━━━━━━━━━━━━━━━
Total Analyses: {statistics.get('total_submissions', 0)}
Completed: {statistics.get('completed_submissions', 0)}
Failed: {statistics.get('failed_submissions', 0)}
Last 24h: {statistics.get('recent_submissions_24h', 0)}

Role Distribution:
{self._format_dict(statistics.get('role_breakdown', {}))}

Recommendations:
{self._format_dict(statistics.get('recommendation_breakdown', {}))}
            """
            
            await self.bot.send_message(
                chat_id=manager_id,
                text=stats_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send recent reports summary
            if reports:
                reports_text = "📋 Recent Analyses:\n\n"
                for i, report in enumerate(reports[:10], 1):
                    # Handle both dict and object formats
                    if isinstance(report.analysis_result, dict):
                        # Calculate score from dict
                        scores = report.analysis_result.get('scores', {})
                        positive_scores = [v for k, v in scores.items() if 'penalty' not in k.lower() and 'critical' not in k.lower()]
                        score = sum(positive_scores) / len(positive_scores) / 100 if positive_scores else 0
                        rec = report.analysis_result.get('recommendation', 'unknown')
                    else:
                        score = report.analysis_result.get_overall_score()
                        rec = report.analysis_result.recommendation.value
                    reports_text += f"{i}. Score: {score:.0%} - {rec}\n"
                    reports_text += f"   _Analyzed {self._format_time_ago(report.created_at)}_\n\n"
                
                await self.bot.send_message(
                    chat_id=manager_id,
                    text=reports_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send manager report: {e}")
            return False
    
    # Helper methods
    
    def _format_architecture_requirements(self, result, role) -> str:
        """Format senior-level architecture requirements check."""
        
        # Helper function to escape HTML
        def escape_html(text: str) -> str:
            if not text:
                return text
            return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Different architecture checks for frontend vs backend
        if role.value == 'frontend':
            # Frontend-specific architecture checks
            # Handle both dict and object formats
            architecture_analysis = None
            if isinstance(result, dict):
                architecture_analysis = result.get('architecture_analysis', None)
            elif hasattr(result, 'architecture_analysis'):
                architecture_analysis = result.architecture_analysis
            
            if architecture_analysis:
                checks_text = ""
                
                # Check App Router
                uses_app_router = architecture_analysis.get('uses_app_router', False)
                checks_text += f"{'✅' if uses_app_router else '❌'} <b>Next.js App Router:</b> {'Yes' if uses_app_router else 'No (Pages Router or missing)'}\n"
                
                # Check File Conventions
                file_conventions = architecture_analysis.get('file_conventions_followed', False)
                checks_text += f"{'✅' if file_conventions else '❌'} <b>File Conventions:</b> {'Followed' if file_conventions else 'Not followed'}\n"
                
                # Check Client Components Implementation
                # Support both old and new field names
                client_components_ok = architecture_analysis.get('client_components_well_structured', 
                                                                architecture_analysis.get('server_client_boundaries_correct', False))
                checks_text += f"{'✅' if client_components_ok else '❌'} <b>Client Components:</b> {'Well-structured' if client_components_ok else 'Needs improvement'}\n"
                
                # Check Routing Structure
                routing = architecture_analysis.get('routing_structure', 'Not analyzed')
                checks_text += f"📁 <b>Routing Structure:</b> {escape_html(routing)}\n"
                
                # Check Component Organization
                organization = architecture_analysis.get('component_organization', 'Not analyzed')
                checks_text += f"📦 <b>Component Organization:</b> {escape_html(organization)}\n"
                
                # Add Folder Structure Analysis if available
                folder_analysis = architecture_analysis.get('folder_structure_analysis', {})
                if folder_analysis:
                    checks_text += "\n<b>📂 Folder Structure Analysis:</b>\n"
                    checks_text += f"  • Components directory: {'✅' if folder_analysis.get('has_components_directory', False) else '❌'}\n"
                    checks_text += f"  • Lib/utils directory: {'✅' if folder_analysis.get('has_lib_directory', False) else '❌'}\n"
                    checks_text += f"  • Component organization: {'✅' if folder_analysis.get('components_properly_organized', False) else '❌'}\n"
                    checks_text += f"  • Utils separation: {'✅' if folder_analysis.get('utils_properly_separated', False) else '❌'}\n"
                    quality = folder_analysis.get('overall_structure_quality', 'unknown')
                    quality_emoji = {'excellent': '🌟', 'good': '✅', 'fair': '⚠️', 'poor': '❌'}.get(quality, '❓')
                    checks_text += f"  • Overall quality: {quality_emoji} {quality.upper()}"
                
                return checks_text
            else:
                return "Frontend architecture analysis not available"
        
        # Backend architecture checks (existing code continues below)
        if role.value != 'backend':
            return "Architecture checks not implemented for this role"
        
        # Extract architecture checks from feedback and penalty breakdown
        # Handle both dict and object formats
        if isinstance(result, dict):
            feedback_lower = result.get('detailed_feedback', '').lower()
        else:
            feedback_lower = result.detailed_feedback.lower() if result.detailed_feedback else ""
        
        # Check for penalty breakdown issues
        issues_text = ""
        # Handle both dict and object formats for penalty_breakdown
        penalty_breakdown = None
        if isinstance(result, dict):
            penalty_breakdown = result.get('penalty_breakdown')
        elif hasattr(result, 'penalty_breakdown'):
            penalty_breakdown = result.penalty_breakdown
        
        if penalty_breakdown:
            issues = penalty_breakdown.get('issues_found', []) if isinstance(penalty_breakdown, dict) else []
            issues_text = " ".join(str(issue.get('issue', '')).lower() for issue in issues if isinstance(issue, dict))
        
        combined_text = feedback_lower + " " + issues_text
        
        # Define what to check with their patterns
        architecture_checks = {
            'architectural_pattern': {
                'name': 'Architectural Pattern',
                'met_patterns': [
                    'layered architecture', 'clean architecture', 'hexagonal', 
                    'mvc', 'mvp', 'mvvm', 'microservice', 'event-driven', 
                    'domain-driven', 'ddd', 'ports and adapters', 'n-tier'
                ],
                'fail_patterns': [
                    'no architecture', 'cannot identify pattern', 
                    'just folders', 'no architectural pattern'
                ]
            },
            'repository_pattern': {
                'name': 'Repository Pattern',
                'met_patterns': [
                    'repository pattern implemented', 'repositories package', 
                    'repository layer', 'data access abstraction',
                    'proper repository', 'repository and service'
                ],
                'fail_patterns': [
                    'missing repository', 'no repository pattern',
                    'no repository layer', 'no repository abstraction',
                    '[enforced] missing repository'
                ]
            },
            'service_layer': {
                'name': 'Service Layer',
                'met_patterns': [
                    'service layer', 'services package', 
                    'business logic separated', 'service pattern'
                ],
                'fail_patterns': [
                    'missing service', 'no service layer',
                    'no service pattern', 'logic in controllers'
                ]
            },
            'redis_implementation': {
                'name': 'Redis Implementation',
                'met_patterns': [
                    'redis for caching', 'redis implementation',
                    'uses redis', 'redis for rate limiting'
                ],
                'fail_patterns': [
                    'missing redis', 'no redis', 
                    'without redis', 'no caching'
                ]
            },
            'database_implementation': {
                'name': 'Database (PostgreSQL/MySQL/MongoDB)',
                'met_patterns': [
                    'postgresql', 'postgres', 'mysql', 'mongodb',
                    'database for persistence', 'proper database'
                ],
                'fail_patterns': [
                    'only in-memory', 'no database', 'missing database',
                    'no proper database', 'in-memory storage only'
                ]
            },
            'dockerization': {
                'name': 'Dockerization',
                'met_patterns': [
                    'dockerfile', 'docker-compose', 'dockerized',
                    'multi-stage docker', 'container', 'docker setup'
                ],
                'fail_patterns': [
                    'missing dockerfile', 'no dockerfile',
                    'missing docker-compose', 'no docker',
                    '[enforced] missing docker'
                ]
            }
        }
        
        # Check each requirement
        checks_text = ""
        all_met = True
        
        for key, check in architecture_checks.items():
            # CRITICAL FIX: Use actual requirements_met data, not text patterns!
            # First check if we have the actual requirement status from analysis
            # Handle both dict and object formats
            requirements_met = None
            if isinstance(result, dict):
                requirements_met = result.get('requirements_met', {})
            elif hasattr(result, 'requirements_met'):
                requirements_met = result.requirements_met
            
            if requirements_met and key in requirements_met:
                # Use the ACTUAL requirement status from LLM analysis
                is_met = requirements_met.get(key, False)
            else:
                # FALLBACK ONLY: Check text patterns if requirements_met not available
                is_met = False
                
                # First check for positive indicators
                for pattern in check['met_patterns']:
                    if pattern in combined_text:
                        is_met = True
                        break
                
                # Then check for negative indicators (overrides positive)
                for pattern in check['fail_patterns']:
                    if pattern in combined_text:
                        is_met = False
                        break
            
            # Format the check result
            symbol = "✓" if is_met else "✗"
            status = "PASS" if is_met else "FAIL"
            
            if not is_met:
                all_met = False
                checks_text += f"<b>{symbol} {escape_html(check['name'])}: <code>{status}</code></b>\n"
            else:
                checks_text += f"{symbol} {escape_html(check['name'])}: <code>{status}</code>\n"
        
        # Add summary
        if not all_met:
            checks_text += "\n<b>⚠️ Missing senior-level requirements detected</b>"
        else:
            checks_text += "\n<b>✅ All senior-level requirements met</b>"
        
        return checks_text
    
    def _format_analysis_report(self, submission: Submission, report: Report) -> str:
        """Format a complete analysis report."""
        result = report.analysis_result
        repo_name = submission.github_url.split('/')[-1].replace('.git', '')
        
        # Calculate overall score
        # Handle both dict and object formats
        if isinstance(result, dict):
            # Calculate from dict scores
            scores = result.get('scores', {})
            positive_scores = [v for k, v in scores.items() if 'penalty' not in k.lower() and 'critical' not in k.lower()]
            overall_score = sum(positive_scores) / len(positive_scores) / 100 if positive_scores else 0
        else:
            overall_score = result.get_overall_score()
        
        # Format scores with progress bars
        def make_progress_bar(score: float) -> str:
            filled = int(score / 10)
            empty = 10 - filled
            return "█" * filled + "░" * empty
        
        # Helper function to escape HTML
        def escape_html(text: str) -> str:
            if not text:
                return text
            return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Format requirements check with penalty information
        requirements_text = ""
        # Handle both dict and object formats
        requirements_met = result.get('requirements_met', {}) if isinstance(result, dict) else result.requirements_met
        penalty_breakdown = result.get('penalty_breakdown') if isinstance(result, dict) else getattr(result, 'penalty_breakdown', None)
        
        for req, met in requirements_met.items():
            symbol = "✓" if met else "✗"
            req_line = f"{symbol} {escape_html(req)}"
            
            # Check for penalties related to this requirement
            if penalty_breakdown and met:  # Only show penalties for met requirements
                issues = penalty_breakdown.get('issues_found', []) if isinstance(penalty_breakdown, dict) else []
                for issue in issues:
                    if isinstance(issue, dict) and req in issue.get('issue', '').lower():
                        penalty_points = issue.get('penalty', 0)
                        if penalty_points > 0:
                            req_line += f" <i>(−{penalty_points}pts penalty)</i>"
                        break
            
            requirements_text += f"{req_line}\n"
        
        # Format strengths and weaknesses with escaped HTML
        # Handle both dict and object formats
        strengths = result.get('strengths', [])[:5] if isinstance(result, dict) else result.strengths[:5]
        weaknesses = result.get('weaknesses', [])[:5] if isinstance(result, dict) else result.weaknesses[:5]
        strengths_text = "\n".join(f"• {escape_html(s)}" for s in strengths)
        weaknesses_text = "\n".join(f"• {escape_html(w)}" for w in weaknesses)
        
        # Determine clear HIRE/NO HIRE decision
        hiring_reason = None
        production_ready = None
        
        # Check if we have hiring_decision from new prompt format
        # Note: result is a dict when loaded from DB, not an AnalysisResult object
        if isinstance(result, dict) and 'hiring_decision' in result and result['hiring_decision']:
            hiring_info = result['hiring_decision']
            hire_decision = hiring_info.get('decision', '').upper()
            hiring_reason = hiring_info.get('primary_reason')
            production_ready = hiring_info.get('is_production_ready')
            
            if hire_decision == 'HIRE':
                decision = "✅ HIRE"
                decision_emoji = "🎯"
                decision_color = "GREEN"
            elif hire_decision == 'NO_HIRE':
                decision = "❌ NO HIRE"
                decision_emoji = "🚫"
                decision_color = "RED"
            else:
                # Fallback to recommendation-based decision
                recommendation = result.get('recommendation', '') if isinstance(result, dict) else result.recommendation.value
                if recommendation in ['strongly_accept', 'accept', 'strong_yes', 'yes']:
                    decision = "✅ HIRE"
                    decision_emoji = "🎯"
                    decision_color = "GREEN"
                elif recommendation == 'review_required':
                    decision = "🔍 REVIEW REQUIRED"
                    decision_emoji = "⚠️"
                    decision_color = "YELLOW"
                else:
                    decision = "❌ NO HIRE"
                    decision_emoji = "🚫"
                    decision_color = "RED"
        else:
            # Old format - use recommendation-based decision
            recommendation = result.get('recommendation', '') if isinstance(result, dict) else result.recommendation.value
            if recommendation in ['strongly_accept', 'accept', 'strong_yes', 'yes']:
                decision = "✅ HIRE"
                decision_emoji = "🎯"
                decision_color = "GREEN"
            elif recommendation == 'review_required':
                decision = "🔍 REVIEW REQUIRED"
                decision_emoji = "⚠️"
                decision_color = "YELLOW"
            else:
                decision = "❌ NO HIRE"
                decision_emoji = "🚫"
                decision_color = "RED"
        
        # Build the report (using HTML format)
        report_text = f"""
📊 <b>CANDIDATE ASSESSMENT REPORT</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 Repository: <code>{escape_html(repo_name)}</code>
💼 Position: {submission.role.value}
📅 Analyzed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}

<b>{decision_emoji} FINAL DECISION: {decision}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Overall Score: {overall_score:.0%}
🔍 Confidence: {(result.get('confidence', 0) if isinstance(result, dict) else result.confidence):.0%}"""
        
        # Add hiring reason and production ready status if available
        if hiring_reason:
            report_text += f"\n📌 <b>Reason:</b> {escape_html(hiring_reason)}"
        if production_ready:
            report_text += f"\n🚀 <b>Production Ready:</b> {escape_html(production_ready)}"
        
        report_text += """

<b>TECHNICAL SCORES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Standard score names we expect
        standard_scores = {
            'task_completion': 'Task Completion',
            'code_quality': 'Code Quality', 
            'seniority_indicators': 'Seniority Indicators',
            'critical_issues_penalty': 'Critical Issues Penalty'
        }
        
        # Handle both dict and object formats
        scores = result.get('scores', {}) if isinstance(result, dict) else result.scores
        for metric, score in scores.items():
            bar = make_progress_bar(score)
            # Use standard name if available, otherwise format the metric name
            if metric in standard_scores:
                metric_display = standard_scores[metric]
            else:
                # Handle any other score names gracefully
                metric_display = metric.replace('_', ' ').title()
            report_text += f"{metric_display:25} {bar} {score:.0f}%\n"
        
        # Add penalty breakdown if available and has actual issues
        # Handle both dict and object formats
        penalty_info = None
        if isinstance(result, dict):
            penalty_info = result.get('penalty_breakdown')
        elif hasattr(result, 'penalty_breakdown'):
            penalty_info = result.penalty_breakdown
        
        if penalty_info:
            issues = penalty_info.get('issues_found', []) if isinstance(penalty_info, dict) else []
            total = penalty_info.get('total_penalty', 0) if isinstance(penalty_info, dict) else 0
            
            # Only show breakdown if we have actual issues to report
            if issues and len(issues) > 0:
                report_text += """

⚠️ <b>CRITICAL ISSUES BREAKDOWN</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
                for issue in issues:
                    if isinstance(issue, dict):
                        issue_text = escape_html(issue.get('issue', 'Unknown issue'))
                        severity = issue.get('severity', 'unknown')
                        penalty = issue.get('penalty', 0)
                        
                        # Severity emoji
                        severity_emoji = {
                            'minor': '🟡',
                            'moderate': '🟠', 
                            'major': '🔴',
                            'critical': '⛔'
                        }.get(severity, '❓')
                        
                        report_text += f"{severity_emoji} {issue_text}\n"
                        report_text += f"   Severity: {severity.upper()} | Penalty: +{penalty} points\n"
                
                report_text += f"\n<b>Total Penalty: {total} points</b>"
                if total > 60:
                    report_text += " <b>(AUTO-REJECT THRESHOLD)</b>"
        
        # Add senior-level architecture requirements section
        architecture_checks = self._format_architecture_requirements(result, submission.role)
        
        report_text += f"""

✅ <b>STRENGTHS</b>
{strengths_text}

⚠️ <b>AREAS FOR IMPROVEMENT</b>
{weaknesses_text}

📝 <b>TASK REQUIREMENTS CHECK</b>
{requirements_text}

🏗️ <b>SENIOR-LEVEL ARCHITECTURE CHECK</b>
{architecture_checks}

💡 <b>EXPLANATION FOR CANDIDATE</b>
{escape_html(result.get('candidate_explanation', result.get('detailed_feedback', 'Analysis completed. Please review the detailed feedback above.')) if isinstance(result, dict) else (result.candidate_explanation if hasattr(result, 'candidate_explanation') and result.candidate_explanation else (result.detailed_feedback if hasattr(result, 'detailed_feedback') else 'Analysis completed. Please review the detailed feedback above.')))}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analysis ID: #{report.id}
Model: {report.model_used}
        """
        
        return report_text.strip()
    
    def _format_report_summary(self, submission: Submission, report: Report) -> str:
        """Format a brief summary of the report."""
        result = report.analysis_result
        # Handle both dict and object formats
        if isinstance(result, dict):
            # Calculate from dict scores
            scores = result.get('scores', {})
            positive_scores = [v for k, v in scores.items() if 'penalty' not in k.lower() and 'critical' not in k.lower()]
            overall_score = sum(positive_scores) / len(positive_scores) / 100 if positive_scores else 0
        else:
            overall_score = result.get_overall_score()
        
        # Determine clear HIRE/NO HIRE decision
        recommendation = result.get('recommendation', '') if isinstance(result, dict) else result.recommendation.value
        # Handle all possible positive recommendations
        if recommendation in ['strongly_accept', 'accept', 'strong_yes', 'yes']:
            decision = "✅ HIRE"
        elif recommendation == 'review_required':
            decision = "🔍 REVIEW REQUIRED (Exception)"
        else:
            decision = "❌ NO HIRE"
        
        return f"""
📊 <b>Analysis Complete!</b>

<b>Decision: {decision}</b>
Score: {overall_score:.0%}
Confidence: {(result.get('confidence', 0) if isinstance(result, dict) else result.confidence):.0%}

<i>Full report follows...</i>
        """
    
    def _split_long_message(self, text: str, max_length: int = 4000) -> List[str]:
        """Split long message into multiple parts."""
        parts = []
        lines = text.split('\n')
        current_part = ""
        
        for line in lines:
            if len(current_part) + len(line) + 1 < max_length:
                current_part += line + '\n'
            else:
                if current_part:
                    parts.append(current_part.strip())
                current_part = line + '\n'
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    def _format_dict(self, d: dict) -> str:
        """Format dictionary for display."""
        if not d:
            return "_No data_"
        return "\n".join(f"• {k}: {v}" for k, v in d.items())
    
    def _format_time_ago(self, dt: datetime) -> str:
        """Format datetime as 'X hours ago' style."""
        if not dt:
            return "unknown time"
        
        diff = datetime.now(timezone.utc) - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"
    
    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown-formatted text to HTML for Telegram."""
        if not text:
            return text
        
        # Escape HTML special characters first
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        # Convert markdown bold to HTML
        import re
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        
        # Convert markdown code blocks to HTML
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        
        # Keep line breaks
        text = text.replace('\n', '\n')
        
        return text
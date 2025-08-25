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
    
    def _format_analysis_report(self, submission: Submission, report: Report) -> str:
        """Format a complete analysis report."""
        result = report.analysis_result
        repo_name = submission.github_url.split('/')[-1].replace('.git', '')
        
        # Calculate overall score
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
        
        # Format requirements check
        requirements_text = ""
        for req, met in result.requirements_met.items():
            symbol = "✓" if met else "✗"
            requirements_text += f"{symbol} {escape_html(req)}\n"
        
        # Format strengths and weaknesses with escaped HTML
        strengths_text = "\n".join(f"• {escape_html(s)}" for s in result.strengths[:5])
        weaknesses_text = "\n".join(f"• {escape_html(w)}" for w in result.weaknesses[:5])
        
        # Determine clear HIRE/NO HIRE decision
        hiring_reason = None
        production_ready = None
        
        # Check if we have hiring_decision from new prompt format
        if hasattr(result, 'hiring_decision') and result.hiring_decision:
            hiring_info = result.hiring_decision
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
                recommendation = result.recommendation.value
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
            recommendation = result.recommendation.value
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
🔍 Confidence: {result.confidence:.0%}"""
        
        # Add hiring reason and production ready status if available
        if hiring_reason:
            report_text += f"\n📌 <b>Reason:</b> {escape_html(hiring_reason)}"
        if production_ready:
            report_text += f"\n🚀 <b>Production Ready:</b> {escape_html(production_ready)}"
        
        report_text += """

<b>TECHNICAL SCORES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        for metric, score in result.scores.items():
            bar = make_progress_bar(score)
            report_text += f"{metric.title():15} {bar} {score:.0f}%\n"
        
        report_text += f"""

✅ <b>STRENGTHS</b>
{strengths_text}

⚠️ <b>AREAS FOR IMPROVEMENT</b>
{weaknesses_text}

📝 <b>KEY REQUIREMENTS CHECK</b>
{requirements_text}

💡 <b>DETAILED FEEDBACK</b>
{escape_html(result.detailed_feedback)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Analysis ID: #{report.id}
Model: {report.model_used}
        """
        
        return report_text.strip()
    
    def _format_report_summary(self, submission: Submission, report: Report) -> str:
        """Format a brief summary of the report."""
        result = report.analysis_result
        overall_score = result.get_overall_score()
        
        # Determine clear HIRE/NO HIRE decision
        recommendation = result.recommendation.value
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
Confidence: {result.confidence:.0%}

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
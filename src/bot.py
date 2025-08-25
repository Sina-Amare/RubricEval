"""
Main Telegram bot for CV Review System.

This module implements the manager-only bot for analyzing candidate repositories.
"""

import asyncio
import sys
from datetime import datetime, timezone
from typing import Optional

# Apply network fixes BEFORE importing telegram
from utils.network_fix import install_network_fixes
install_network_fixes()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError

# Add imports from our modules
from config import BOT_TOKEN, MANAGER_IDS
from core.models import Submission, Role, SubmissionStatus
from core.exceptions import ValidationError, RepositoryError, AnalysisError
from adapters.storage.sqlite import SQLiteAdapter
from adapters.repositories.github import GitHubAdapter
from adapters.analyzers.openrouter import OpenRouterAdapter
from adapters.notifications.telegram import TelegramAdapter
from utils.logger import setup_logger, log_error_with_context
from utils.validators import validate_github_url

# Initialize logger
logger = setup_logger(__name__)

# Conversation states
WAITING_FOR_URL = 1
WAITING_FOR_ROLE = 2

# Initialize adapters (will be done in main)
storage_adapter = None
repo_adapter = None
analyzer_adapter = None
notification_adapter = None


# Command handlers

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    logger.info(f"Start command from user {user.username} ({user.id})")
    
    welcome_message = """
👋 Welcome to CV Review Bot!

I help you analyze candidate GitHub repositories quickly and consistently.

**How to use:**
1. Type /analyze to start
2. Send me the GitHub repository URL
3. Select the position (Backend/Frontend)
4. Get detailed analysis in 2-5 minutes

**Commands:**
/analyze - Start new analysis
/recent - View recent analyses (last 10)
/history - View all analysis history
/historyfrontend - Frontend analyses only
/historybackend - Backend analyses only
/report - View specific report (use: /report 12)
/stats - View statistics
/help - Show this message
/cancel - Cancel current operation
    """
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await start_command(update, context)


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the analysis conversation."""
    user = update.effective_user
    logger.info(f"Analyze command from user {user.username} ({user.id})")
    
    # Check if user is authorized (optional - remove if all users should have access)
    if MANAGER_IDS and str(user.id) not in MANAGER_IDS:
        await update.message.reply_text(
            "❌ You are not authorized to use this bot.\n"
            "Please contact the administrator."
        )
        return ConversationHandler.END
    
    prompt_message = """
📝 Please send me the GitHub repository URL for analysis.

**Example formats:**
• `https://github.com/username/repository`
• `https://github.com/username/repo.git`
    """
    
    await update.message.reply_text(
        prompt_message,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return WAITING_FOR_URL


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle URL submission."""
    user = update.effective_user
    url = update.message.text.strip()
    
    logger.info(f"Received URL from {user.username}: {url}")
    
    # Validate URL format
    is_valid, error_msg = validate_github_url(url)
    
    if not is_valid:
        # Provide helpful error message
        if "github.com" not in url.lower():
            error_response = """
❌ That doesn't appear to be a GitHub URL.

I can only analyze GitHub repositories.
Please send a GitHub URL like:
`https://github.com/username/repository`

Try again:
            """
        else:
            error_response = """
❌ The URL format seems incorrect.

Please check the URL format:
✓ `https://github.com/username/repo`
✓ `https://github.com/username/repo.git`

Try again:
            """
        
        await update.message.reply_text(
            error_response,
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_FOR_URL
    
    # Store URL in context for next step
    context.user_data['github_url'] = url
    
    # Try to validate repository accessibility
    await update.message.reply_chat_action(ChatAction.TYPING)
    
    try:
        # Quick check if repository exists and is accessible
        is_accessible = await repo_adapter.validate_url(url)
        
        if not is_accessible:
            await update.message.reply_text(
                "⚠️ I couldn't access this repository. Please check:\n"
                "• Is the repository public?\n"
                "• Is the URL correct?\n"
                "• Does the repository exist?\n\n"
                "Please send the URL again or type /cancel to stop.",
                parse_mode=ParseMode.MARKDOWN
            )
            return WAITING_FOR_URL
        
    except Exception as e:
        logger.warning(f"Error checking repository accessibility: {e}")
        # Continue anyway - will fail later with better error
    
    # Extract repository info including branch
    from utils.validators import extract_github_info
    username, repo_name, branch = extract_github_info(url)
    owner_repo = f"{username}/{repo_name}"
    
    # Ask for role selection
    if branch:
        message = f"""
✅ Repository found: `{owner_repo}` (branch: `{branch}`)

Which position is this candidate applying for?
    """
    else:
        message = f"""
✅ Repository found: `{owner_repo}`

Which position is this candidate applying for?
    """
    
    keyboard = [
        [
            InlineKeyboardButton("👨‍💻 Backend Developer", callback_data="role_backend"),
            InlineKeyboardButton("🎨 Frontend Developer", callback_data="role_frontend")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    return WAITING_FOR_ROLE


async def role_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle role selection callback."""
    query = update.callback_query
    user = query.from_user
    
    # Acknowledge the callback
    await query.answer()
    
    # Get role from callback data
    role_str = query.data.replace("role_", "")
    role = Role.BACKEND if role_str == "backend" else Role.FRONTEND
    
    # Get stored URL
    github_url = context.user_data.get('github_url')
    
    if not github_url:
        await query.edit_message_text(
            "❌ Session expired. Please start again with /analyze"
        )
        return ConversationHandler.END
    
    logger.info(f"Starting analysis for {github_url} as {role.value}")
    
    # Update message to show processing
    await query.edit_message_text(
        f"🔄 Analyzing repository for {role.value} position...\n"
        f"This typically takes 2-5 minutes.\n\n"
        f"Repository: `{github_url.split('/')[-1]}`\n"
        f"Position: {role.value}\n"
        f"Status: Processing...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Start the analysis in background
    asyncio.create_task(
        process_analysis(
            query.message.chat_id,
            user.id,
            user.username,
            github_url,
            role,
            context
        )
    )
    
    return ConversationHandler.END


async def process_analysis(
    chat_id: int,
    user_id: int,
    username: str,
    github_url: str,
    role: Role,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Process the repository analysis.
    
    This runs as a background task to avoid blocking the bot.
    """
    progress_message = None  # Store message to edit/delete later
    
    try:
        # Check for existing submission with same URL and role
        existing = await storage_adapter.find_existing_submission(
            github_url=github_url,
            role=role.value,
            user_id=str(user_id)
        )
        
        if existing:
            # Delete the old submission and its report
            logger.info(f"Found existing submission {existing.id}, removing it")
            await storage_adapter.delete_submission_and_report(existing.id)
            
            # Notify user we're replacing the old analysis
            await context.bot.send_message(
                chat_id=chat_id,
                text="ℹ️ Found previous analysis for this repository. Replacing with new analysis..."
            )
        
        # Create new submission record
        submission = Submission(
            telegram_user_id=str(user_id),
            telegram_username=username or "Unknown",
            github_url=github_url,
            role=role,
            status=SubmissionStatus.PENDING
        )
        
        submission = await storage_adapter.create_submission(submission)
        logger.info(f"Created submission {submission.id}")
        
        # Update status to analyzing
        await storage_adapter.update_submission(
            submission.id,
            status=SubmissionStatus.ANALYZING
        )
        
        # Send initial progress message (will be edited)
        progress_message = await context.bot.send_message(
            chat_id=chat_id,
            text="📥 Fetching repository content..."
        )
        
        # Fetch repository
        try:
            repo_content = await repo_adapter.fetch_repository(github_url, role)
            logger.info(f"Fetched repository: {len(repo_content.files)} files")
        except RepositoryError as e:
            raise Exception(f"Repository error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to fetch repository: {str(e)}")
        
        # Edit progress message instead of sending new one
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_message.message_id,
            text=f"🔍 Analyzing {len(repo_content.files)} files..."
        )
        
        # Load task requirements
        task_file = f"data/task_requirements/{role.value}_task.md"
        try:
            with open(task_file, 'r') as f:
                task_requirements = f.read()
        except FileNotFoundError:
            logger.warning(f"Task file not found: {task_file}")
            task_requirements = f"Analyze this {role.value} repository for code quality and completeness."
        
        # Create analysis request
        from core.models import AnalysisRequest
        analysis_request = AnalysisRequest(
            repository_content=repo_content,
            role=role,
            task_requirements=task_requirements,
            github_url=github_url,
            submission_id=submission.id
        )
        
        # Perform analysis
        try:
            analysis_result = await analyzer_adapter.analyze_code(analysis_request)
            logger.info(f"Analysis complete for submission {submission.id}")
        except AnalysisError as e:
            raise Exception(f"Analysis error: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to analyze code: {str(e)}")
        
        # Create report
        from core.models import Report
        report = Report(
            submission_id=submission.id,
            analysis_result=analysis_result,
            model_used=analyzer_adapter.models[0]['name'] if analyzer_adapter.models else "unknown",
            tokens_used=repo_content.total_tokens,
            analysis_duration=60  # TODO: Track actual duration
        )
        
        report = await storage_adapter.create_report(report)
        logger.info(f"Created report {report.id}")
        
        # Update submission status
        await storage_adapter.update_submission(
            submission.id,
            status=SubmissionStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc)
        )
        
        # Delete progress message before sending results
        if progress_message:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=progress_message.message_id
                )
            except:
                pass  # Ignore if message already deleted
        
        # Send results
        await notification_adapter.send_analysis_complete(
            str(chat_id),
            submission,
            report
        )
        
        # Send separator for clarity
        await context.bot.send_message(
            chat_id=chat_id,
            text="━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Analysis failed for {github_url}: {error_msg}")
        log_error_with_context(logger, e, {'url': github_url, 'role': role.value})
        
        # Delete progress message if exists
        if progress_message:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=progress_message.message_id
                )
            except:
                pass
        
        # Update submission as failed
        try:
            if submission and submission.id:
                await storage_adapter.update_submission(
                    submission.id,
                    status=SubmissionStatus.FAILED,
                    error_message=error_msg[:500],  # Truncate long errors
                    completed_at=datetime.now(timezone.utc)
                )
        except Exception as db_error:
            logger.error(f"Could not update submission status: {db_error}")
            # Continue anyway - user notification is more important
        
        # Send user-friendly error message with recovery instructions
        try:
            recovery_message = (
                "❌ **Analysis Failed**\n\n"
                f"Repository: `{github_url.split('/')[-1]}`\n"
                f"Position: {role.value}\n\n"
                "The analysis could not be completed. This might be due to:\n"
                "• Repository is too large\n"
                "• Network connectivity issues\n"
                "• Temporary API unavailability\n\n"
                "**What to do:**\n"
                "1️⃣ Use /cancel to reset\n"
                "2️⃣ Try again with /analyze\n"
                "3️⃣ If it's a large repo, try a smaller one\n\n"
                "The bot is still running and ready for your next request!"
            )
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=recovery_message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as notify_error:
            logger.error(f"Could not send error notification: {notify_error}")
            # Even if we can't notify, don't crash - just log it
    
    finally:
        # Clean up repository adapter
        await repo_adapter.cleanup()


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent analyses."""
    user = update.effective_user
    logger.info(f"Recent command from user {user.username} ({user.id})")
    
    try:
        # Get recent reports
        reports = await storage_adapter.get_recent_reports(limit=10)
        
        if not reports:
            await update.message.reply_text(
                "📋 No recent analyses found.\n\n"
                "Use /analyze to start a new analysis."
            )
            return
        
        # Format report list
        message = "📋 **Recent Analyses:**\n\n"
        
        for i, report in enumerate(reports, 1):
            # Get submission details
            submission = await storage_adapter.get_submission(report.submission_id)
            if submission:
                repo_name = submission.github_url.split('/')[-1].replace('.git', '')
                role = submission.role.value
            else:
                repo_name = "Unknown"
                role = "Unknown"
            
            score = report.analysis_result.get_overall_score()
            rec = report.analysis_result.recommendation.value.replace('_', ' ').upper()
            
            # Format time - handle both timezone-aware and naive datetimes
            if report.created_at:
                # Ensure report.created_at is timezone-aware
                if report.created_at.tzinfo is None:
                    # If naive, assume it's UTC
                    report_time = report.created_at.replace(tzinfo=timezone.utc)
                else:
                    report_time = report.created_at
                
                time_diff = datetime.now(timezone.utc) - report_time
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}d ago"
                elif time_diff.seconds > 3600:
                    time_str = f"{time_diff.seconds // 3600}h ago"
                else:
                    time_str = f"{time_diff.seconds // 60}m ago"
            else:
                time_str = "Unknown"
            
            message += f"{i}. `{repo_name}` ({role})\n"
            message += f"   Score: {score:.0%} - {rec}\n"
            message += f"   _Analyzed {time_str}_\n\n"
        
        message += "_Use /analyze to start a new analysis_"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in recent command: {e}")
        await update.message.reply_text(
            "❌ Error retrieving recent analyses.\n"
            "Please try again later."
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show statistics."""
    user = update.effective_user
    logger.info(f"Stats command from user {user.username} ({user.id})")
    
    try:
        # Get statistics
        stats = await storage_adapter.get_statistics()
        
        # Format statistics message using HTML to avoid markdown parsing issues
        message = f"""
📊 <b>System Statistics</b>
━━━━━━━━━━━━━━━━━━━━

<b>Overall:</b>
• Total Analyses: {stats.get('total_submissions', 0)}
• Completed: {stats.get('completed_submissions', 0)}
• Failed: {stats.get('failed_submissions', 0)}
• Last 24h: {stats.get('recent_submissions_24h', 0)}

<b>By Position:</b>
        """
        
        role_breakdown = stats.get('role_breakdown', {})
        for role, count in role_breakdown.items():
            message += f"• {role.title()}: {count}\n"
        
        message += "\n<b>Recommendations:</b>\n"
        rec_breakdown = stats.get('recommendation_breakdown', {})
        for rec, count in rec_breakdown.items():
            # Replace underscores with spaces for better display
            rec_display = rec.replace('_', ' ').upper()
            message += f"• {rec_display}: {count}\n"
        
        if 'average_confidence' in stats and stats['average_confidence']:
            confidence_pct = int(stats['average_confidence'] * 100)
            message += f"\n<b>Average Confidence:</b> {confidence_pct}%"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await update.message.reply_text(
            "❌ Error retrieving statistics.\n"
            "Please try again later."
        )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    user = update.effective_user
    logger.info(f"Cancel command from user {user.username} ({user.id})")
    
    # Clear user data
    context.user_data.clear()
    
    await update.message.reply_text(
        "❌ Operation cancelled.\n\n"
        "Use /analyze to start a new analysis."
    )
    
    return ConversationHandler.END


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show paginated history of analyses with filtering."""
    user = update.effective_user
    logger.info(f"History command from user {user.username} ({user.id})")
    
    # Check if user is manager
    if MANAGER_IDS and str(user.id) not in MANAGER_IDS:
        await update.message.reply_text(
            "❌ This command is only available to managers."
        )
        return
    
    # Parse arguments for role filter
    role_filter = None
    page = 0
    
    if context.args:
        arg = context.args[0].lower()
        if arg in ['frontend', 'backend']:
            role_filter = Role.FRONTEND if arg == 'frontend' else Role.BACKEND
    
    # Store filter in context for pagination
    context.user_data['history_role_filter'] = role_filter
    context.user_data['history_page'] = page
    
    await show_history_page(update, context, page, role_filter)


async def history_frontend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show paginated history of frontend analyses."""
    user = update.effective_user
    logger.info(f"History frontend command from user {user.username} ({user.id})")
    
    # Check if user is manager
    if MANAGER_IDS and str(user.id) not in MANAGER_IDS:
        await update.message.reply_text(
            "❌ This command is only available to managers."
        )
        return
    
    # Set frontend filter
    role_filter = Role.FRONTEND
    page = 0
    
    # Store filter in context for pagination
    context.user_data['history_role_filter'] = role_filter
    context.user_data['history_page'] = page
    
    await show_history_page(update, context, page, role_filter)


async def history_backend_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show paginated history of backend analyses."""
    user = update.effective_user
    logger.info(f"History backend command from user {user.username} ({user.id})")
    
    # Check if user is manager
    if MANAGER_IDS and str(user.id) not in MANAGER_IDS:
        await update.message.reply_text(
            "❌ This command is only available to managers."
        )
        return
    
    # Set backend filter
    role_filter = Role.BACKEND
    page = 0
    
    # Store filter in context for pagination
    context.user_data['history_role_filter'] = role_filter
    context.user_data['history_page'] = page
    
    await show_history_page(update, context, page, role_filter)


async def show_history_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int, role_filter: Optional[Role] = None) -> None:
    """Display a page of history results."""
    ITEMS_PER_PAGE = 5
    
    try:
        # Get all reports with optional role filter
        all_reports = await storage_adapter.get_all_reports(limit=100, role=role_filter)
        
        if not all_reports:
            text = "📋 No analyses found"
            if role_filter:
                text += f" for {role_filter.value} position"
            
            # Check if this is from callback or direct command
            if update.callback_query:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        # Calculate pagination
        total_pages = (len(all_reports) - 1) // ITEMS_PER_PAGE + 1
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(all_reports))
        page_reports = all_reports[start_idx:end_idx]
        
        # Build message using HTML format to avoid markdown parsing issues
        message = f"📊 <b>Analysis History</b>"
        if role_filter:
            message += f" - {role_filter.value.upper()}"
        message += f"\nPage {page + 1}/{total_pages}\n\n"
        
        for report in page_reports:
            # Get submission details
            submission = await storage_adapter.get_submission(report.submission_id)
            if submission:
                repo_name = submission.github_url.split('/')[-1].replace('.git', '')
                username = submission.telegram_username or "Unknown"
                
                # Format time
                if report.created_at:
                    if report.created_at.tzinfo is None:
                        report_time = report.created_at.replace(tzinfo=timezone.utc)
                    else:
                        report_time = report.created_at
                    time_str = report_time.strftime("%Y-%m-%d %H:%M")
                else:
                    time_str = "Unknown"
                
                score = report.analysis_result.get_overall_score()
                rec = report.analysis_result.recommendation.value.replace('_', ' ').title()
                
                # HTML escape for safety
                from html import escape
                safe_repo = escape(repo_name)
                safe_username = escape(username)
                
                message += f"<b>#{report.id}</b> <code>{safe_repo}</code>\n"
                message += f"👤 {safe_username} | 💼 {submission.role.value}\n"
                message += f"📊 Score: {score:.0%} | {rec}\n"
                message += f"🕐 {time_str}\n"
                message += "─" * 30 + "\n"
        
        # Create inline keyboard for pagination and viewing
        keyboard = []
        
        # View buttons for each report
        view_buttons = []
        for report in page_reports:
            view_buttons.append(
                InlineKeyboardButton(
                    f"View #{report.id}",
                    callback_data=f"view_report_{report.id}"
                )
            )
        
        # Add view buttons in rows of 2
        for i in range(0, len(view_buttons), 2):
            row = view_buttons[i:i+2]
            keyboard.append(row)
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"history_prev_{page}")
            )
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"history_next_{page}")
            )
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # Filter buttons
        filter_buttons = []
        if role_filter != Role.FRONTEND:
            filter_buttons.append(
                InlineKeyboardButton("🎨 Frontend Only", callback_data="history_filter_frontend")
            )
        if role_filter != Role.BACKEND:
            filter_buttons.append(
                InlineKeyboardButton("⚙️ Backend Only", callback_data="history_filter_backend")
            )
        if role_filter is not None:
            filter_buttons.append(
                InlineKeyboardButton("📋 Show All", callback_data="history_filter_all")
            )
        
        if filter_buttons:
            keyboard.append(filter_buttons)
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        # Send or edit message with HTML parse mode
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Error in history display: {e}")
        error_text = "❌ Error retrieving history. Please try again."
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)


async def history_navigation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle history navigation callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    role_filter = context.user_data.get('history_role_filter')
    current_page = context.user_data.get('history_page', 0)
    
    if data.startswith("history_prev_"):
        new_page = max(0, current_page - 1)
    elif data.startswith("history_next_"):
        new_page = current_page + 1
    elif data == "history_filter_frontend":
        role_filter = Role.FRONTEND
        new_page = 0
    elif data == "history_filter_backend":
        role_filter = Role.BACKEND
        new_page = 0
    elif data == "history_filter_all":
        role_filter = None
        new_page = 0
    elif data == "history_back":
        # Return to history from report view
        new_page = context.user_data.get('history_page', 0)
    else:
        return
    
    context.user_data['history_role_filter'] = role_filter
    context.user_data['history_page'] = new_page
    
    await show_history_page(update, context, new_page, role_filter)


async def view_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle viewing individual report."""
    query = update.callback_query
    await query.answer()
    
    # Extract report ID
    report_id = int(query.data.split('_')[-1])
    
    try:
        # Get report from database
        report = await storage_adapter.get_report(report_id)
        if not report:
            await query.edit_message_text("❌ Report not found.")
            return
        
        # Get submission details
        submission = await storage_adapter.get_submission(report.submission_id)
        if not submission:
            await query.edit_message_text("❌ Submission data not found.")
            return
        
        # Helper function to escape HTML
        def escape_html(text: str) -> str:
            if not text:
                return text
            return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Format the detailed report using HTML
        repo_name = escape_html(submission.github_url.split('/')[-1].replace('.git', ''))
        score = report.analysis_result.get_overall_score()
        
        message = f"""📊 <b>DETAILED ANALYSIS REPORT #{report.id}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>Repository:</b> <code>{repo_name}</code>
<b>URL:</b> {escape_html(submission.github_url)}
<b>Position:</b> {submission.role.value}
<b>Candidate:</b> {escape_html(submission.telegram_username)}
<b>Date:</b> {report.created_at.strftime("%Y-%m-%d %H:%M") if report.created_at else "Unknown"}

<b>SCORES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Add individual scores
        for score_name, score_value in report.analysis_result.scores.items():
            score_display = score_name.replace('_', ' ').title()
            bar = "█" * int(score_value / 10) + "░" * (10 - int(score_value / 10))
            message += f"{score_display}: {bar} {score_value:.0f}%\n"
        
        message += f"\n<b>Overall Score:</b> {score:.0%}\n"
        
        # Check if we have hiring_decision from new prompt format
        if hasattr(report.analysis_result, 'hiring_decision') and report.analysis_result.hiring_decision:
            hiring_info = report.analysis_result.hiring_decision
            hire_decision = hiring_info.get('decision', '').upper()
            
            if hire_decision == 'HIRE':
                decision = "✅ <b>HIRE</b>"
                decision_emoji = "🎯"
            elif hire_decision == 'NO_HIRE':
                decision = "❌ <b>NO HIRE</b>"
                decision_emoji = "🚫"
            else:
                # Fallback to recommendation-based decision
                recommendation = report.analysis_result.recommendation.value
                if recommendation in ['strongly_accept', 'accept', 'strong_yes', 'yes']:
                    decision = "✅ <b>HIRE</b>"
                    decision_emoji = "🎯"
                elif recommendation == 'review_required':
                    decision = "🔍 <b>REVIEW REQUIRED</b>"
                    decision_emoji = "⚠️"
                else:
                    decision = "❌ <b>NO HIRE</b>"
                    decision_emoji = "🚫"
            
            message += f"\n{decision_emoji} <b>FINAL DECISION: {decision}</b>\n"
            
            # Add hiring reason if available
            if hiring_info.get('primary_reason'):
                message += f"<b>Reason:</b> {escape_html(hiring_info['primary_reason'])}\n"
            
            if hiring_info.get('is_production_ready'):
                message += f"<b>Production Ready:</b> {escape_html(str(hiring_info['is_production_ready']))}\n"
        else:
            # Old format - use recommendation-based decision
            recommendation = report.analysis_result.recommendation.value
            if recommendation in ['strongly_accept', 'accept', 'strong_yes', 'yes']:
                decision = "✅ <b>HIRE</b>"
                decision_emoji = "🎯"
            elif recommendation == 'review_required':
                decision = "🔍 <b>REVIEW REQUIRED</b> (Exception Case)"
                decision_emoji = "⚠️"
            else:
                decision = "❌ <b>NO HIRE</b>"
                decision_emoji = "🚫"
            
            message += f"\n{decision_emoji} <b>FINAL DECISION: {decision}</b>\n"
        
        message += f"<b>Confidence:</b> {int(report.analysis_result.confidence * 100)}%\n"
        
        # Add strengths
        if report.analysis_result.strengths:
            message += "\n<b>STRENGTHS</b>\n"
            for strength in report.analysis_result.strengths[:5]:
                message += f"✅ {escape_html(strength)}\n"
        
        # Add weaknesses
        if report.analysis_result.weaknesses:
            message += "\n<b>WEAKNESSES</b>\n"
            for weakness in report.analysis_result.weaknesses[:5]:
                message += f"⚠️ {escape_html(weakness)}\n"
        
        # Check if message is getting too long
        if len(message) > 3500:  # Leave room for feedback
            # Send main report first
            await query.edit_message_text(
                text=message + "\n\n<i>Detailed feedback follows...</i>",
                parse_mode=ParseMode.HTML
            )
            
            # Send detailed feedback as a separate message
            if report.analysis_result.detailed_feedback:
                feedback_message = f"<b>DETAILED FEEDBACK (continued)</b>\n\n{escape_html(report.analysis_result.detailed_feedback)}"
                
                # Split feedback if it's too long
                if len(feedback_message) > 4000:
                    # Send in chunks
                    chunks = []
                    words = feedback_message.split(' ')
                    current_chunk = ""
                    
                    for word in words:
                        if len(current_chunk) + len(word) + 1 < 4000:
                            current_chunk += word + " "
                        else:
                            chunks.append(current_chunk.strip())
                            current_chunk = word + " "
                    
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await context.bot.send_message(
                                chat_id=query.message.chat_id,
                                text=chunk,
                                parse_mode=ParseMode.HTML
                            )
                        else:
                            await context.bot.send_message(
                                chat_id=query.message.chat_id,
                                text=f"<i>(continued)</i>\n\n{chunk}",
                                parse_mode=ParseMode.HTML
                            )
                else:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=feedback_message,
                        parse_mode=ParseMode.HTML
                    )
            
            # Send back button as final message
            keyboard = [[
                InlineKeyboardButton("⬅️ Back to History", callback_data="history_back")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                reply_markup=reply_markup
            )
        else:
            # Message is short enough, include everything
            if report.analysis_result.detailed_feedback:
                feedback = report.analysis_result.detailed_feedback
                # Allow more space for feedback when message is shorter
                max_feedback_len = 4000 - len(message) - 50  # Leave some buffer
                if len(feedback) > max_feedback_len:
                    feedback = feedback[:max_feedback_len-3] + "..."
                message += f"\n<b>DETAILED FEEDBACK</b>\n{escape_html(feedback)}\n"
            
            # Add back button
            keyboard = [[
                InlineKeyboardButton("⬅️ Back to History", callback_data="history_back")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        
    except Exception as e:
        logger.error(f"Error viewing report {report_id}: {e}")
        await query.edit_message_text(f"❌ Error viewing report: {str(e)}")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View a specific report by ID."""
    user = update.effective_user
    logger.info(f"Report command from user {user.username} ({user.id})")
    
    # Check if user is manager
    if MANAGER_IDS and str(user.id) not in MANAGER_IDS:
        await update.message.reply_text(
            "❌ This command is only available to managers."
        )
        return
    
    # Get report ID from arguments
    if not context.args:
        await update.message.reply_text(
            "Please provide a report ID.\n"
            "Usage: /report <ID>\n"
            "Example: /report 5"
        )
        return
    
    try:
        report_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Invalid report ID. Please provide a number.\n"
            "Example: /report 5"
        )
        return
    
    # Create a fake callback query to reuse the view_report_callback
    class FakeQuery:
        def __init__(self, data):
            self.data = data
        async def answer(self):
            pass
        async def edit_message_text(self, **kwargs):
            await update.message.reply_text(**kwargs)
    
    update.callback_query = FakeQuery(f"view_report_{report_id}")
    await view_report_callback(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot - NEVER let the bot crash."""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Always try to notify user with helpful recovery message
    try:
        if update and hasattr(update, 'effective_chat'):
            error_message = (
                "❌ An unexpected error occurred.\n\n"
                "Please try the following:\n"
                "1️⃣ Use /cancel to reset\n"
                "2️⃣ Start fresh with /analyze\n\n"
                "If the problem persists, please try again in a few moments."
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_message
            )
    except Exception as e:
        logger.error(f"Could not send error message to user: {e}")
        # Even if we can't notify the user, DON'T CRASH
        pass
    
    # Log the full error for debugging
    import traceback
    logger.error(f"Full traceback:\n{''.join(traceback.format_tb(context.error.__traceback__))}")
    
    # IMPORTANT: Return None to indicate error was handled
    # This prevents the error from propagating and crashing the bot
    return None


async def initialize_adapters():
    """Initialize all adapters."""
    global storage_adapter, repo_adapter, analyzer_adapter, notification_adapter
    
    logger.info("Initializing adapters...")
    
    # Initialize storage
    storage_adapter = SQLiteAdapter()
    await storage_adapter.initialize()
    logger.info("Storage adapter initialized")
    
    # Initialize repository adapter
    repo_adapter = GitHubAdapter()
    logger.info("Repository adapter initialized")
    
    # Initialize analyzer
    analyzer_adapter = OpenRouterAdapter()
    logger.info("Analyzer adapter initialized")
    
    # Initialize notification adapter
    notification_adapter = TelegramAdapter()
    await notification_adapter.initialize()
    logger.info("Notification adapter initialized")


def main() -> None:
    """Main function to run the bot."""
    logger.info("Starting CV Review Bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Set up conversation handler for analyze command
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_command)],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)],
            WAITING_FOR_ROLE: [CallbackQueryHandler(role_callback, pattern="^role_")]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        per_chat=False  # Disable per_chat to avoid issues
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("historyfrontend", history_frontend_command))
    application.add_handler(CommandHandler("historybackend", history_backend_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(history_navigation_callback, pattern="^history_"))
    application.add_handler(CallbackQueryHandler(view_report_callback, pattern="^view_report_"))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Initialize adapters before starting
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(initialize_adapters())
    
    # Delete any existing webhook to avoid conflicts (with retry)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            loop.run_until_complete(application.bot.delete_webhook(drop_pending_updates=True))
            logger.info("Cleared any existing webhooks")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Failed to delete webhook (attempt {attempt + 1}/{max_retries}): {e}")
                import time
                time.sleep(2)
            else:
                logger.error(f"Could not delete webhook after {max_retries} attempts: {e}")
                # Continue anyway - polling might still work
    
    logger.info("Bot is ready! Starting polling...")
    
    # Start the bot with proper configuration
    application.run_polling(
        drop_pending_updates=True,
        close_loop=False
    )


if __name__ == "__main__":
    import signal
    import os
    import time
    import traceback
    
    # PID file to track running instance
    PID_FILE = "/tmp/cv_review_bot.pid"
    
    def cleanup_and_exit(signum=None, frame=None):
        """Clean shutdown handler."""
        logger.info("Shutting down bot gracefully...")
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except:
            pass
        sys.exit(0)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, cleanup_and_exit)
    signal.signal(signal.SIGINT, cleanup_and_exit)
    
    # Check if another instance is running
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process is still running
            os.kill(old_pid, 0)
            
            # Process exists, try to kill it
            logger.warning(f"Found existing bot process (PID: {old_pid}), stopping it...")
            try:
                os.kill(old_pid, signal.SIGTERM)
                time.sleep(2)  # Give it time to shutdown gracefully
            except:
                pass
                
        except (ProcessLookupError, ValueError):
            # Process doesn't exist or invalid PID, safe to continue
            pass
        except Exception as e:
            logger.warning(f"Error checking PID file: {e}")
    
    # Write current PID
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error(f"Could not write PID file: {e}")
    
    # MAIN LOOP WITH AUTOMATIC RECOVERY
    # The bot will NEVER exit due to errors - it will always try to recover
    restart_count = 0
    max_restart_delay = 60  # Maximum delay between restarts (seconds)
    
    while True:
        try:
            logger.info(f"Starting bot (attempt #{restart_count + 1})...")
            main()
            # If main() returns normally (shouldn't happen), break the loop
            logger.info("Bot exited normally")
            break
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C)")
            cleanup_and_exit()
            break
            
        except Exception as e:
            restart_count += 1
            
            # Log the error with full traceback
            logger.error(f"Bot crashed with error: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Calculate restart delay with exponential backoff
            # Starts at 5 seconds, doubles each time, max 60 seconds
            restart_delay = min(5 * (2 ** min(restart_count - 1, 5)), max_restart_delay)
            
            logger.warning(f"Bot will restart in {restart_delay} seconds (attempt #{restart_count + 1})...")
            logger.warning("The bot will keep trying to recover automatically.")
            
            # Wait before restarting
            time.sleep(restart_delay)
            
            # Reset restart count after 10 successful minutes
            # This is handled by the main() function running for a while
            
            logger.info("Attempting to restart bot...")
            # Continue the loop to restart the bot